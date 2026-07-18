"""Tests for the OWN verb engine (agent/verbs/own.py) — all filesystem via
tmp_path, all HTTP-adjacent seams mocked through ``agent.tools.comfy_api.handle``.
No real ComfyUI, no network, no API key."""

import json
from unittest.mock import patch

import pytest

from agent.tools import comfy_api, comfy_inspect
from agent.verbs import own


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_models(tmp_path):
    """Fake models directory with two folders and one zero-byte file."""
    models = tmp_path / "models"
    models.mkdir()

    ckpts = models / "checkpoints"
    ckpts.mkdir()
    (ckpts / "dreamshaper_v8.safetensors").write_bytes(b"\x00" * 2048)
    (ckpts / "sdxl_base_1.0.safetensors").write_bytes(b"\x00" * 4096)
    (ckpts / "broken_download.safetensors").write_bytes(b"")  # zero-byte

    loras = models / "loras"
    loras.mkdir()
    (loras / "style_sdxl.safetensors").write_bytes(b"\x00" * 512)
    return models


@pytest.fixture
def fake_custom_nodes(tmp_path):
    """Fake Custom_Nodes directory including the bridge pack."""
    cn = tmp_path / "Custom_Nodes"
    cn.mkdir()
    (cn / "comfyui-impact-pack").mkdir()
    (cn / "comfy_agent_bridge").mkdir()
    return cn


@pytest.fixture
def fake_sessions(tmp_path):
    """Fake sessions dir: two outcome files (one with a malformed line)."""
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    lines = [
        json.dumps({"success": True}),
        "not json {",
        json.dumps({"success": False}),
        json.dumps({"rating": 4}),
    ]
    (sdir / "default_outcomes.jsonl").write_text("\n".join(lines), encoding="utf-8")
    (sdir / "demo_outcomes.jsonl").write_text(json.dumps({"success": True}), encoding="utf-8")
    (sdir / "notes.jsonl").write_text("{}", encoding="utf-8")  # ignored — wrong suffix
    return sdir


def _write_diag(root, status="completed", findings=None, triggers=None):
    """Drop one diagnosis document under root in the date-dir layout."""
    day = root / "2026-07-18"
    day.mkdir(parents=True, exist_ok=True)
    doc = {
        "envHash": "abcd1234" * 4,
        "diagnosisId": "d1",
        "nodeId": "box",
        "createdAt": "2026-07-18T10:00:00Z",
        "run": {"status": status, "workflowHash": "w" * 32, "durationS": 1.0, "stages": []},
        "triggers": triggers or [],
        "findings": findings or [],
    }
    (day / "abcd1234_d1.json").write_text(json.dumps(doc), encoding="utf-8")


def _fake_api(running=True, stats=None):
    """A stand-in for comfy_api.handle covering both seams OWN uses."""

    def fake_handle(name, tool_input):
        if name == "is_comfyui_running":
            if running:
                return json.dumps(
                    {"running": True, "url": "http://127.0.0.1:8188", "gpu": "RTX 4090"}
                )
            return json.dumps(
                {
                    "running": False,
                    "url": "http://127.0.0.1:8188",
                    "error": "ComfyUI is not running at http://127.0.0.1:8188.",
                }
            )
        if name == "get_system_stats":
            if stats is None:
                return json.dumps({"error": "Could not connect to ComfyUI. Is it running?"})
            return json.dumps(stats)
        return json.dumps({"error": f"Unknown tool: {name}"})

    return fake_handle


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


class TestDoctorReport:
    def test_all_green(self, fake_models, fake_custom_nodes, tmp_path, monkeypatch):
        _write_diag(tmp_path / "diag")
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "diag"))
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch.object(comfy_api, "handle", _fake_api(running=True)),
        ):
            report = own.doctor_report()
        assert report["ok"] is True
        names = [c["name"] for c in report["checks"]]
        assert names == [
            "comfyui",
            "models_folder",
            "custom_nodes_folder",
            "bridge_pack",
            "last_run_report",
        ]
        assert all(c["ok"] for c in report["checks"])
        assert "healthy" in report["summary"]

    def test_comfyui_down_is_finding_not_error(
        self, fake_models, fake_custom_nodes, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "diag"))
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch.object(comfy_api, "handle", _fake_api(running=False)),
        ):
            report = own.doctor_report()  # must not raise
        comfy = report["checks"][0]
        assert comfy["ok"] is False
        assert comfy["fix_hint"]
        assert report["ok"] is False
        # the on-disk checks still ran and passed
        assert report["checks"][1]["ok"] is True
        assert report["checks"][2]["ok"] is True

    def test_missing_dirs_and_bridge(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "diag"))
        cn = tmp_path / "Custom_Nodes"
        cn.mkdir()
        (cn / "some-utils").mkdir()  # no bridge pack
        with (
            patch.object(comfy_inspect, "MODELS_DIR", tmp_path / "nope"),
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", cn),
            patch.object(comfy_api, "handle", _fake_api(running=True)),
        ):
            report = own.doctor_report()
        by_name = {c["name"]: c for c in report["checks"]}
        assert by_name["models_folder"]["ok"] is False
        assert "COMFYUI_DATABASE" in by_name["models_folder"]["fix_hint"]
        assert by_name["bridge_pack"]["ok"] is False
        assert "comfy_agent_bridge" in by_name["bridge_pack"]["fix_hint"]

    def test_no_diagnose_reports_is_ok(
        self, fake_models, fake_custom_nodes, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "empty_diag"))
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch.object(comfy_api, "handle", _fake_api(running=True)),
        ):
            report = own.doctor_report()
        last = report["checks"][-1]
        assert last["ok"] is True
        assert "No run reports yet" in last["note"]

    def test_bad_last_run_surfaces_verdict(
        self, fake_models, fake_custom_nodes, tmp_path, monkeypatch
    ):
        _write_diag(
            tmp_path / "diag",
            status="error",
            triggers=["execution_error"],
            findings=[{"severity": "critical", "code": "OOM", "explanation": "ran out"}],
        )
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "diag"))
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch.object(comfy_api, "handle", _fake_api(running=True)),
        ):
            report = own.doctor_report()
        last = report["checks"][-1]
        assert last["ok"] is False
        assert "cozy diagnose --last" in last["fix_hint"]

    def test_never_raises_even_when_seams_explode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "diag"))
        with (
            patch.object(comfy_inspect, "MODELS_DIR", tmp_path / "no_models"),
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", tmp_path / "no_cn"),
            patch.object(comfy_api, "handle", side_effect=RuntimeError("boom")),
        ):
            report = own.doctor_report()
        assert len(report["checks"]) == 5
        assert report["checks"][0]["ok"] is False

    def test_render(self, fake_models, fake_custom_nodes, tmp_path, monkeypatch):
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "diag"))
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch.object(comfy_api, "handle", _fake_api(running=False)),
        ):
            text = own.render_doctor_report(own.doctor_report())
        assert text.startswith("Cozy doctor")
        assert own.GLYPH_MISSING in text
        assert "fix:" in text


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

_STATS = {
    "system": {"python_version": "3.11.9"},
    "devices": [
        {
            "name": "NVIDIA RTX 4090",
            "type": "cuda",
            "vram_total": 24 * 1024**3,
            "vram_free": 20 * 1024**3,
        },
    ],
}


class TestStatsReport:
    def test_models_sessions_and_gpu(self, fake_models, fake_sessions):
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_api, "handle", _fake_api(stats=_STATS)),
        ):
            report = own.stats_report(sessions_dir=fake_sessions)
        by_type = {t["model_type"]: t for t in report["models"]["by_type"]}
        assert by_type["checkpoints"]["count"] == 3
        assert by_type["loras"]["count"] == 1
        assert report["models"]["total_count"] == 4
        assert report["models"]["total_size_bytes"] == 2048 + 4096 + 512

        sessions = {s["session"]: s["outcomes"] for s in report["sessions"]["sessions"]}
        assert sessions == {"default": 3, "demo": 1}  # malformed line skipped
        assert report["sessions"]["total_outcomes"] == 4

        gpu = report["gpu"]
        assert gpu["available"] is True
        assert gpu["devices"][0]["name"] == "NVIDIA RTX 4090"
        assert gpu["devices"][0]["vram_total"] == "24.0 GB"
        assert gpu["devices"][0]["vram_used"] == "4.0 GB"

    def test_degraded_when_comfyui_down(self, fake_models, fake_sessions):
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_api, "handle", _fake_api(stats=None)),
        ):
            report = own.stats_report(sessions_dir=fake_sessions)
        assert report["gpu"]["available"] is False
        assert "not running" in report["gpu"]["note"]
        assert report["models"]["total_count"] == 4  # on-disk stats unaffected

    def test_no_sessions_dir(self, fake_models, tmp_path):
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_api, "handle", _fake_api(stats=None)),
        ):
            report = own.stats_report(sessions_dir=tmp_path / "nope")
        assert report["sessions"]["sessions"] == []
        assert "No session history yet" in report["sessions"]["note"]

    def test_render(self, fake_models, fake_sessions):
        with (
            patch.object(comfy_inspect, "MODELS_DIR", fake_models),
            patch.object(comfy_api, "handle", _fake_api(stats=_STATS)),
        ):
            text = own.render_stats_report(own.stats_report(sessions_dir=fake_sessions))
        assert "Models —" in text
        assert "checkpoints" in text
        assert "default: 3 outcome(s)" in text
        assert "NVIDIA RTX 4090" in text


# ---------------------------------------------------------------------------
# Model search (local disk only — OQ-4 offline index deferred)
# ---------------------------------------------------------------------------


class TestSearchModels:
    def test_substring_match_is_deterministic(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            result = own.search_models("sdxl")
        names = [m["name"] for m in result["matches"]]
        assert names == ["sdxl_base_1.0.safetensors", "style_sdxl.safetensors"]
        assert result["matches"][0]["model_type"] == "checkpoints"
        assert result["matches"][1]["model_type"] == "loras"
        assert result["note"] is None

    def test_folder_name_matches_too(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            result = own.search_models("checkpoints")
        assert len(result["matches"]) == 3  # every model in the checkpoints folder

    def test_fuzzy_match_survives_separator_differences(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            result = own.search_models("dreamshaper v8")  # space, not underscore
        names = [m["name"] for m in result["matches"]]
        assert "dreamshaper_v8.safetensors" in names
        top = result["matches"][0]
        assert top["score"] < 0.8  # difflib branch, not substring

    def test_zero_byte_model_keeps_attention_glyph(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            result = own.search_models("broken_download")
        assert result["matches"][0]["status"] == "attention"

    def test_empty_query_gets_usage_note(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            result = own.search_models("   ")
        assert result["matches"] == []
        assert "part of a model name" in result["note"]

    def test_no_match_note_mentions_disk_only(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            result = own.search_models("zzzzqq")
        assert result["matches"] == []
        assert "disk only" in result["note"]

    def test_missing_models_folder_note(self, tmp_path):
        with patch.object(comfy_inspect, "MODELS_DIR", tmp_path / "nope"):
            result = own.search_models("sdxl")
        assert result["matches"] == []
        assert "No models folder" in result["note"]

    def test_render(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            text = own.render_search_report(own.search_models("sdxl"))
        assert "matching 'sdxl'" in text
        assert "sdxl_base_1.0.safetensors" in text
        assert own.GLYPH_OK in text
