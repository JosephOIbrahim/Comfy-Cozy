"""C-R12 crucible — download_model resume, progress, and informed confirm.

Covers: Range-header resume (206 append), whole-file SHA-256 on resume (seeded
hasher), Range-ignored restart (200), partial KEPT on transient failure, the
20 GB cap counting the resumed offset, the enriched zero-network confirm
payload, the exists-check sitting BEFORE the confirm gate, per-chunk progress
reporting, and the dispatcher's signature-aware progress forwarding.

Network is mocked at httpx.stream (same seam as test_comfy_provision.py); the
final-hop DNS re-validation is stubbed so tests stay hermetic.
"""

import contextlib
import hashlib
import json
from unittest.mock import patch

import httpx
import pytest

from agent.tools import comfy_provision

_URL = "https://huggingface.co/repo/resolve/main/model.safetensors"


class _FakeResponse:
    """Minimal httpx streaming-response stand-in."""

    def __init__(self, status_code, chunks=None, headers=None, exc=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []
        self._exc = exc  # raised AFTER the chunks — simulates a mid-stream failure

    def iter_bytes(self, chunk_size):
        for chunk in self._chunks:
            yield chunk
        if self._exc is not None:
            raise self._exc


class _StreamRecorder:
    """Stands in for httpx.stream; records request kwargs, yields a fake response."""

    def __init__(self, response):
        self._response = response
        self.calls = []

    @contextlib.contextmanager
    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        yield self._response


class _ProgressSpy:
    def __init__(self):
        self.calls = []

    def report(self, progress, total=None, message=None):
        self.calls.append((progress, total, message))


@pytest.fixture()
def fake_models(tmp_path):
    models = tmp_path / "models"
    (models / "checkpoints").mkdir(parents=True)
    return models


def _paths(fake_models):
    target = fake_models / "checkpoints" / "model.safetensors"
    return target, target.with_suffix(target.suffix + ".download")


def _download(fake_models, stream, extra=None, progress=None):
    args = {
        "url": _URL,
        "model_type": "checkpoints",
        "filename": "model.safetensors",
        "confirm": True,
    }
    if extra:
        args.update(extra)
    with patch.object(comfy_provision, "MODELS_DIR", fake_models), \
         patch("agent.tools.comfy_provision.httpx.stream", stream), \
         patch("agent.tools.comfy_provision._resolve_and_check_private",
               return_value=None):
        return json.loads(comfy_provision._handle_download_model(args, progress=progress))


# ---------------------------------------------------------------------------
# (a) Resume: Range header sent, 206 appends to the partial
# ---------------------------------------------------------------------------

class TestRangeResume:
    def test_partial_sends_range_and_206_appends(self, fake_models):
        target, temp = _paths(fake_models)
        temp.write_bytes(b"OLDBYTES")
        rec = _StreamRecorder(_FakeResponse(
            206, chunks=[b"NEWBYTES"], headers={"content-length": "8"},
        ))
        result = _download(fake_models, rec)
        assert "error" not in result, result
        assert rec.calls[0]["headers"] == {"Range": "bytes=8-"}
        assert target.read_bytes() == b"OLDBYTESNEWBYTES"
        assert result["resumed_from_bytes"] == 8
        assert not temp.exists()

    def test_no_partial_sends_no_range(self, fake_models):
        target, _ = _paths(fake_models)
        rec = _StreamRecorder(_FakeResponse(200, chunks=[b"FRESH"]))
        result = _download(fake_models, rec)
        assert "error" not in result, result
        assert rec.calls[0]["headers"] is None
        assert target.read_bytes() == b"FRESH"
        assert "resumed_from_bytes" not in result

    # ------------------------------------------------------------------
    # (c) Server ignores Range (200) — restart from zero
    # ------------------------------------------------------------------

    def test_server_ignores_range_restarts_from_zero(self, fake_models):
        target, temp = _paths(fake_models)
        temp.write_bytes(b"STALEPARTIAL")
        rec = _StreamRecorder(_FakeResponse(200, chunks=[b"FULLCONTENT"]))
        result = _download(fake_models, rec)
        assert "error" not in result, result
        assert rec.calls[0]["headers"] == {"Range": "bytes=12-"}  # Range WAS sent
        assert target.read_bytes() == b"FULLCONTENT"              # ...but 200 restarted clean
        assert "resumed_from_bytes" not in result


# ---------------------------------------------------------------------------
# (b) Resume SHA verify covers the WHOLE file (seeded hasher)
# ---------------------------------------------------------------------------

class TestResumeShaVerify:
    def test_206_sha_covers_whole_file(self, fake_models):
        target, temp = _paths(fake_models)
        temp.write_bytes(b"OLDBYTES")
        full_sha = hashlib.sha256(b"OLDBYTESNEWBYTES").hexdigest()
        result = _download(
            fake_models, _StreamRecorder(_FakeResponse(206, chunks=[b"NEWBYTES"])),
            extra={"expected_sha256": full_sha},
        )
        assert "error" not in result, result
        assert target.read_bytes() == b"OLDBYTESNEWBYTES"

    def test_206_sha_of_new_bytes_only_mismatches_and_unlinks(self, fake_models):
        # digest of ONLY the new bytes must NOT match the seeded whole-file hash
        target, temp = _paths(fake_models)
        temp.write_bytes(b"OLDBYTES")
        wrong_sha = hashlib.sha256(b"NEWBYTES").hexdigest()
        result = _download(
            fake_models, _StreamRecorder(_FakeResponse(206, chunks=[b"NEWBYTES"])),
            extra={"expected_sha256": wrong_sha},
        )
        assert "mismatch" in result.get("error", "").lower(), result
        assert not target.exists()
        assert not temp.exists()  # SHA mismatch still unlinks the partial


# ---------------------------------------------------------------------------
# (d) Transient failures KEEP the partial — that is the point of resume
# ---------------------------------------------------------------------------

class TestTransientFailureKeepsPartial:
    def test_timeout_midstream_keeps_partial(self, fake_models):
        target, temp = _paths(fake_models)
        resp = _FakeResponse(200, chunks=[b"PARTIALDATA"],
                             exc=httpx.TimeoutException("mid-stream timeout"))
        result = _download(fake_models, _StreamRecorder(resp))
        assert "timed out" in result["error"].lower(), result
        assert temp.exists() and temp.read_bytes() == b"PARTIALDATA"
        assert not target.exists()

    def test_connect_error_keeps_existing_partial(self, fake_models):
        _, temp = _paths(fake_models)
        temp.write_bytes(b"OLDBYTES")

        def _refuse(method, url, **kwargs):
            raise httpx.ConnectError("connection refused")

        result = _download(fake_models, _refuse)
        assert "error" in result, result
        assert temp.read_bytes() == b"OLDBYTES"  # partial KEPT for the next resume


# ---------------------------------------------------------------------------
# (e) 20 GB cap counts resumed offset + new bytes
# ---------------------------------------------------------------------------

class TestCapCountsResumedOffset:
    def test_cap_includes_resumed_offset(self, fake_models):
        target, temp = _paths(fake_models)
        temp.write_bytes(b"X" * 8)
        # cap=10: 8 resumed + 4 new = 12 > 10 must abort; 4 alone would pass
        with patch.object(comfy_provision, "_MAX_DOWNLOAD_BYTES", 10):
            result = _download(
                fake_models, _StreamRecorder(_FakeResponse(206, chunks=[b"Y" * 4])),
            )
        assert "safety limit" in result.get("error", ""), result
        assert not target.exists()


# ---------------------------------------------------------------------------
# (f) Unconfirmed call: enriched payload, ZERO network
# ---------------------------------------------------------------------------

class TestInformedConfirm:
    def test_unconfirmed_enriched_payload_zero_network(self, fake_models):
        target, temp = _paths(fake_models)
        temp.write_bytes(b"OLDBYTES")
        with patch.object(comfy_provision, "MODELS_DIR", fake_models), \
             patch("agent.tools.comfy_provision.httpx.stream") as stream:
            result = json.loads(comfy_provision._handle_download_model({
                "url": _URL, "model_type": "checkpoints",
                "filename": "model.safetensors",
            }))
        stream.assert_not_called()
        assert result["status"] == "needs_confirmation"
        assert result["host"] == "huggingface.co"
        assert result["destination"] == str(target)
        assert result["model_type"] == "checkpoints"
        assert result["resume_available"] is True
        assert result["resume_from_bytes"] == 8

    def test_unconfirmed_without_partial_reports_no_resume(self, fake_models):
        with patch.object(comfy_provision, "MODELS_DIR", fake_models), \
             patch("agent.tools.comfy_provision.httpx.stream") as stream:
            result = json.loads(comfy_provision._handle_download_model({
                "url": _URL, "model_type": "checkpoints",
                "filename": "model.safetensors",
            }))
        stream.assert_not_called()
        assert result["status"] == "needs_confirmation"
        assert result["resume_available"] is False
        assert "resume_from_bytes" not in result

    # ------------------------------------------------------------------
    # (g) exists-check sits BEFORE the confirm gate
    # ------------------------------------------------------------------

    def test_existing_target_answers_before_confirm_gate(self, fake_models):
        target, _ = _paths(fake_models)
        target.write_bytes(b"ALREADY")
        with patch.object(comfy_provision, "MODELS_DIR", fake_models), \
             patch("agent.tools.comfy_provision.httpx.stream") as stream:
            # NOTE: no confirm — the local exists-check must answer first
            result = json.loads(comfy_provision._handle_download_model({
                "url": _URL, "model_type": "checkpoints",
                "filename": "model.safetensors",
            }))
        stream.assert_not_called()
        assert "already exists" in result.get("error", ""), result
        assert result.get("status") != "needs_confirmation"


# ---------------------------------------------------------------------------
# (h) Progress callback: monotonically increasing byte counts
# ---------------------------------------------------------------------------

class TestProgressReporting:
    def test_progress_reports_monotonic_byte_counts(self, fake_models):
        chunks = [b"a" * 10, b"b" * 20, b"c" * 30]
        resp = _FakeResponse(200, chunks=chunks, headers={"content-length": "60"})
        spy = _ProgressSpy()
        with patch.object(comfy_provision, "MODELS_DIR", fake_models), \
             patch("agent.tools.comfy_provision.httpx.stream", _StreamRecorder(resp)), \
             patch("agent.tools.comfy_provision._resolve_and_check_private",
                   return_value=None):
            # via handle() — exercises the new progress kwarg threading too
            result = json.loads(comfy_provision.handle(
                "download_model",
                {"url": _URL, "model_type": "checkpoints",
                 "filename": "model.safetensors", "confirm": True},
                progress=spy,
            ))
        assert "error" not in result, result
        done = [c[0] for c in spy.calls]
        assert done == [10, 30, 60]                # monotonically increasing bytes
        assert all(c[1] == 60 for c in spy.calls)  # total = offset(0) + content-length

    def test_resume_progress_includes_offset_in_total(self, fake_models):
        _, temp = _paths(fake_models)
        temp.write_bytes(b"OLDBYTES")  # 8 bytes
        resp = _FakeResponse(206, chunks=[b"NEWBYTES"], headers={"content-length": "8"})
        spy = _ProgressSpy()
        result = _download(fake_models, _StreamRecorder(resp), progress=spy)
        assert "error" not in result, result
        assert [c[0] for c in spy.calls] == [16]   # resumed 8 + new 8
        assert spy.calls[0][1] == 16               # total = offset + content-length


# ---------------------------------------------------------------------------
# Dispatcher: signature-aware progress forwarding (no double execution)
# ---------------------------------------------------------------------------

class TestSignatureAwareDispatch:
    def test_progress_aware_detection_cached(self):
        import agent.tools as tools_pkg
        from agent.tools import comfy_execute, workflow_parse
        assert tools_pkg._handle_accepts_progress(comfy_execute) is True
        assert tools_pkg._handle_accepts_progress(comfy_provision) is True
        assert tools_pkg._handle_accepts_progress(workflow_parse) is False
        # cached after first computation
        assert tools_pkg._PROGRESS_AWARE[comfy_execute.__name__] is True
        assert tools_pkg._PROGRESS_AWARE[workflow_parse.__name__] is False

    def test_internal_typeerror_runs_handler_exactly_once(self, monkeypatch):
        """A TypeError raised INSIDE a progress-accepting handler must NOT
        trigger a second (progress-less) execution — the old try/except-
        TypeError forwarding re-ran the handler in exactly this case."""
        import agent.tools as tools_pkg

        calls = []

        class _Mod:
            __name__ = "_fake_c_r12_mod"

            @staticmethod
            def handle(name, tool_input, progress=None):
                calls.append(name)
                raise TypeError("bug INSIDE the handler")

        monkeypatch.setitem(tools_pkg._HANDLERS, "list_workflow_templates", _Mod)
        tools_pkg._PROGRESS_AWARE.pop("_fake_c_r12_mod", None)
        try:
            result = tools_pkg.handle("list_workflow_templates", {})
        finally:
            tools_pkg._PROGRESS_AWARE.pop("_fake_c_r12_mod", None)
        assert calls == ["list_workflow_templates"], "handler must run exactly once"
        assert "error" in result.lower() or "wrong" in result.lower()
