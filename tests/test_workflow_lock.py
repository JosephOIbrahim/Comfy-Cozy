"""workflow.lock sidecar — build, write-on-save, drift warnings (hardening 3.8)."""

import hashlib
import json
import os
from unittest.mock import patch

import pytest

from agent.tools import workflow_lock as wl


WORKFLOW = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd15.safetensors"}},
    "2": {"class_type": "KSampler", "inputs": {"seed": 42}},
    "3": {"class_type": "FancyCustomNode", "inputs": {}},
}


@pytest.fixture(autouse=True)
def _clear_hash_cache():
    wl._hash_cache.clear()
    yield
    wl._hash_cache.clear()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Fake MODELS_DIR + CUSTOM_NODES_DIR + pack index + live version."""
    models = tmp_path / "models" / "checkpoints"
    models.mkdir(parents=True)
    ckpt = models / "sd15.safetensors"
    ckpt.write_bytes(b"model-bytes-v1")

    packs = tmp_path / "Custom_Nodes"
    pack = packs / "fancy-pack"
    git = pack / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text("a" * 40 + "\n", encoding="utf-8")

    monkeypatch.setattr(wl, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(wl, "CUSTOM_NODES_DIR", packs)

    index = {"FancyCustomNode": {"url": "https://github.com/x/fancy-pack", "title": "Fancy"}}
    p_index = patch("agent.tools.comfy_discover._build_node_to_pack", return_value=index)
    p_ver = patch.object(wl, "_live_comfyui_version", return_value="0.24.0")
    with p_index, p_ver:
        yield {"ckpt": ckpt, "pack_main": git / "refs" / "heads" / "main", "tmp": tmp_path}


class TestBuildLock:
    def test_pins_model_hash_pack_commit_and_version(self, env):
        lock = wl.build_lock(WORKFLOW, b"wf-bytes")
        m = lock["models"]["sd15.safetensors"]
        assert m["sha256"] == hashlib.sha256(b"model-bytes-v1").hexdigest()
        assert m["size"] == len(b"model-bytes-v1")
        assert lock["packs"]["Fancy"]["commit"] == "a" * 40
        assert lock["packs"]["Fancy"]["dir"] == "fancy-pack"
        assert lock["comfyui_version"] == "0.24.0"
        assert lock["workflow_sha256"] == hashlib.sha256(b"wf-bytes").hexdigest()
        # core nodes (KSampler, CheckpointLoaderSimple) get no pack entry
        assert list(lock["packs"]) == ["Fancy"]

    def test_missing_model_marked_not_fatal(self, env):
        wf = {"1": {"class_type": "KSampler", "inputs": {"ckpt_name": "nope.safetensors"}}}
        lock = wl.build_lock(wf, b"x")
        assert lock["models"]["nope.safetensors"] == {"missing": True}

    def test_detached_head_and_packed_refs(self, env):
        git = env["tmp"] / "Custom_Nodes" / "fancy-pack" / ".git"
        # detached HEAD: the commit is in HEAD itself
        (git / "HEAD").write_text("b" * 40 + "\n", encoding="utf-8")
        assert wl._read_git_commit(git.parent) == "b" * 40
        # packed-refs fallback
        (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (git / "refs" / "heads" / "main").unlink()
        (git / "packed-refs").write_text(
            "# pack-refs\n" + "c" * 40 + " refs/heads/main\n", encoding="utf-8"
        )
        assert wl._read_git_commit(git.parent) == "c" * 40

    def test_hash_reused_from_prior_lock_when_stat_matches(self, env):
        first = wl.build_lock(WORKFLOW, b"x")
        wl._hash_cache.clear()
        calls = {"n": 0}
        real = hashlib.sha256

        def counting(*a, **k):
            calls["n"] += 1
            return real(*a, **k)

        with patch.object(wl.hashlib, "sha256", side_effect=counting):
            second = wl.build_lock(WORKFLOW, b"x", prior_lock=first)
        m = second["models"]["sd15.safetensors"]
        assert m["sha256"] == first["models"]["sd15.safetensors"]["sha256"]
        # one sha256() call for workflow_bytes only — the model hash was reused
        assert calls["n"] == 1


class TestDrift:
    def _write_pair(self, env):
        wf_path = env["tmp"] / "shot.json"
        body = json.dumps(WORKFLOW).encode("utf-8")
        wf_path.write_bytes(body)
        wl.write_lock_sidecar(wf_path, WORKFLOW, body)
        return wf_path

    def test_no_sidecar_is_silent(self, env):
        assert wl.check_lock_drift(env["tmp"] / "absent.json") == []

    def test_unchanged_environment_no_warnings(self, env):
        wf_path = self._write_pair(env)
        assert wl.check_lock_drift(wf_path) == []

    def test_model_content_drift_warns(self, env):
        wf_path = self._write_pair(env)
        env["ckpt"].write_bytes(b"model-bytes-v2-different")
        warns = wl.check_lock_drift(wf_path)
        assert len(warns) == 1 and "drifted since lock" in warns[0]
        assert "sd15.safetensors" in warns[0]

    def test_touched_but_identical_model_stays_quiet(self, env):
        wf_path = self._write_pair(env)
        st = env["ckpt"].stat()
        os.utime(env["ckpt"], ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        wl._hash_cache.clear()
        assert wl.check_lock_drift(wf_path) == []  # re-hash confirms no change

    def test_pack_commit_drift_warns(self, env):
        wf_path = self._write_pair(env)
        env["pack_main"].write_text("d" * 40 + "\n", encoding="utf-8")
        warns = wl.check_lock_drift(wf_path)
        assert len(warns) == 1 and "Fancy" in warns[0] and "drifted" in warns[0]

    def test_comfyui_version_drift_warns(self, env):
        wf_path = self._write_pair(env)
        with patch.object(wl, "_live_comfyui_version", return_value="0.25.1"):
            warns = wl.check_lock_drift(wf_path)
        assert len(warns) == 1 and "ComfyUI drifted" in warns[0]


class TestSeams:
    def test_save_workflow_writes_sidecar(self, env, sample_workflow_file):
        from agent.tools import workflow_patch
        workflow_patch.handle("apply_workflow_patch", {
            "path": str(sample_workflow_file), "patches": [],
        })
        out = env["tmp"] / "saved.json"
        result = json.loads(workflow_patch.handle("save_workflow", {
            "output_path": str(out),
        }))
        assert result["saved"] == str(out)
        assert result.get("lock") == str(wl.lock_path_for(out))
        lock = json.loads(wl.lock_path_for(out).read_text(encoding="utf-8"))
        assert lock["schema"] == wl.LOCK_SCHEMA
        assert "sd15.safetensors" in lock["models"]

    def test_lock_failure_never_fails_the_save(self, env, sample_workflow_file):
        from agent.tools import workflow_patch
        workflow_patch.handle("apply_workflow_patch", {
            "path": str(sample_workflow_file), "patches": [],
        })
        out = env["tmp"] / "saved2.json"
        with patch.object(wl, "build_lock", side_effect=RuntimeError("boom")):
            result = json.loads(workflow_patch.handle("save_workflow", {
                "output_path": str(out),
            }))
        assert result["saved"] == str(out)
        assert "boom" in result.get("lock_error", "")
        assert out.exists()

    def test_validate_surfaces_drift_warnings(self, env, sample_workflow_file):
        from agent.tools import comfy_execute
        wf_path = env["tmp"] / "shot.json"
        body = json.dumps(WORKFLOW).encode("utf-8")
        wf_path.write_bytes(body)
        wl.write_lock_sidecar(wf_path, WORKFLOW, body)
        env["ckpt"].write_bytes(b"model-bytes-v2-different")

        object_info = {
            "CheckpointLoaderSimple": {"input": {"required": {}}},
            "KSampler": {"input": {"required": {}}},
            "FancyCustomNode": {"input": {"required": {}}},
        }
        with patch("agent.tools.comfy_api._get", return_value=object_info):
            result = json.loads(comfy_execute.handle("validate_before_execute", {
                "path": str(wf_path),
            }))
        assert result["valid"] is True
        assert any("drifted since lock" in w for w in result.get("warnings", []))
