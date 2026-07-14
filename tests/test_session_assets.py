"""Tests for REMEMBER v1 workflow-asset extraction (agent/memory/session.py).

Pure, local, deterministic extraction of checkpoints / LoRAs / VAEs / models /
seeds from an API-format workflow, plus the v2->v3 backfill migration. No
ComfyUI, no network, no cognitive stage — the CLEAR REMEMBER path only.
"""

import json

from agent.memory import session as S

EMPTY = {"checkpoints": [], "loras": [], "vaes": [], "models": [], "seeds": []}


def _api_workflow() -> dict:
    """A minimal SDXL + LoRA + VAE + KSampler API-format graph."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
        },
        "2": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "add_detail.safetensors",
                "model": ["1", 0],
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "sdxl_vae.safetensors"},
        },
        "4": {
            "class_type": "KSampler",
            "inputs": {"seed": 42, "steps": 20, "model": ["2", 0]},
        },
    }


class TestExtractWorkflowAssets:
    def test_extracts_each_asset_class(self):
        a = S._extract_workflow_assets(_api_workflow())
        assert a["checkpoints"] == ["sd_xl_base_1.0.safetensors"]
        assert a["loras"] == ["add_detail.safetensors"]
        assert a["vaes"] == ["sdxl_vae.safetensors"]
        assert a["seeds"] == [42]
        assert a["models"] == []  # nothing residual in a clean SDXL graph

    def test_none_and_non_dict_are_empty(self):
        assert S._extract_workflow_assets(None) == EMPTY
        assert S._extract_workflow_assets("nope") == EMPTY
        assert S._extract_workflow_assets([]) == EMPTY

    def test_dedupes_and_sorts(self):
        wf = {
            "a": {"inputs": {"ckpt_name": "b.safetensors"}},
            "b": {"inputs": {"ckpt_name": "a.safetensors"}},
            "c": {"inputs": {"ckpt_name": "b.safetensors"}},  # duplicate
        }
        assert S._extract_workflow_assets(wf)["checkpoints"] == [
            "a.safetensors",
            "b.safetensors",
        ]

    def test_connection_inputs_and_bool_seed_ignored(self):
        wf = {"a": {"inputs": {"model": ["x", 0], "seed": True, "vae_name": ["y", 0]}}}
        a = S._extract_workflow_assets(wf)
        assert a["seeds"] == []  # bool is not a real seed
        assert a["vaes"] == []  # connection ref, not a filename
        assert a["checkpoints"] == []
        assert a["models"] == []

    def test_multiple_seeds_sorted(self):
        wf = {
            "a": {"inputs": {"seed": 99}},
            "b": {"inputs": {"noise_seed": 7}},
        }
        assert S._extract_workflow_assets(wf)["seeds"] == [7, 99]

    def test_randomize_seed_sentinel_skipped(self):
        # -1 is the ComfyUI "randomize each run" sentinel — it does not
        # reproduce a look, so it is not recorded as a remembered seed.
        wf = {"a": {"inputs": {"seed": -1}}, "b": {"inputs": {"noise_seed": 5}}}
        assert S._extract_workflow_assets(wf)["seeds"] == [5]

    def test_lora_wins_over_extension_bucket(self):
        # a lora_name ending in .safetensors lands in loras, not checkpoints
        wf = {"a": {"inputs": {"lora_name": "style.safetensors"}}}
        a = S._extract_workflow_assets(wf)
        assert a["loras"] == ["style.safetensors"]
        assert a["checkpoints"] == []
        assert a["models"] == []

    def test_residual_models_bucket_not_mislabeled_checkpoint(self):
        # ControlNet / upscaler / generic model files are honest residue in
        # "models", NOT mislabeled as checkpoints.
        wf = {
            "a": {"inputs": {"control_net_name": "canny.safetensors"}},
            "b": {"inputs": {"model_name": "4x-UltraSharp.pth"}},
            "c": {"inputs": {"unet_name": "flux1-dev.safetensors"}},
        }
        a = S._extract_workflow_assets(wf)
        assert a["checkpoints"] == ["flux1-dev.safetensors"]  # unet hint
        assert a["models"] == ["4x-UltraSharp.pth", "canny.safetensors"]

    def test_malformed_nodes_and_nonstring_keys_tolerated(self):
        wf = {
            "a": "not-a-dict",
            "b": {"inputs": "also-not-a-dict"},
            "c": {},
            "d": {"inputs": {123: "weird.safetensors"}},  # non-string key
        }
        assert S._extract_workflow_assets(wf) == EMPTY


class TestSerializeIncludesAssets:
    def test_serialize_none_state_has_empty_assets(self):
        wf = S._serialize_workflow_state(None)
        assert wf["assets"] == EMPTY

    def test_serialize_extracts_from_current(self):
        state = {
            "loaded_path": "x.json",
            "format": "api",
            "base_workflow": {},
            "current_workflow": _api_workflow(),
            "history": [],
        }
        wf = S._serialize_workflow_state(state)
        assert wf["assets"]["checkpoints"] == ["sd_xl_base_1.0.safetensors"]
        assert wf["assets"]["seeds"] == [42]

    def test_serialize_falls_back_to_base(self):
        state = {
            "loaded_path": "x.json",
            "format": "api",
            "base_workflow": _api_workflow(),
            "current_workflow": None,
            "history": [],
        }
        wf = S._serialize_workflow_state(state)
        assert wf["assets"]["loras"] == ["add_detail.safetensors"]


class TestEmptySessionCarriesAssets:
    def test_empty_session_has_assets_key(self):
        # add_note() on a fresh name creates an _empty_session — it must carry
        # the assets field so the "v3 always has assets" invariant holds.
        empty = S._empty_session("fresh")
        assert empty["workflow"]["assets"] == EMPTY
        assert empty["schema_version"] == S.SCHEMA_VERSION

    def test_add_note_created_session_has_assets_on_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr(S, "SESSIONS_DIR", tmp_path)
        S.add_note("fresh", "hello", note_type="tip")
        loaded = S.load_session("fresh")
        assert loaded["workflow"]["assets"] == EMPTY


class TestSaveLoadRoundTripAssets:
    def test_round_trip_persists_assets(self, tmp_path, monkeypatch):
        monkeypatch.setattr(S, "SESSIONS_DIR", tmp_path)
        state = {
            "loaded_path": "x.json",
            "format": "api",
            "base_workflow": {},
            "current_workflow": _api_workflow(),
            "history": [],
        }
        res = S.save_session("portrait-v2", workflow_state=state)
        assert "saved" in res
        loaded = S.load_session("portrait-v2")
        assert loaded["workflow"]["assets"]["checkpoints"] == ["sd_xl_base_1.0.safetensors"]
        assert loaded["schema_version"] == S.SCHEMA_VERSION


class TestMigrationBackfillsAssets:
    def test_v2_session_gains_assets_on_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr(S, "SESSIONS_DIR", tmp_path)
        # a v2 session written before REMEMBER v1 — no 'assets' key
        old = {
            "name": "legacy",
            "saved_at": "2026-01-01T00:00:00",
            "schema_version": 2,
            "workflow": {
                "loaded_path": "x.json",
                "format": "api",
                "base_workflow": {},
                "current_workflow": _api_workflow(),
                "history_depth": 0,
            },
            "notes": [],
            "metadata": {},
        }
        (tmp_path / "legacy.json").write_text(json.dumps(old), encoding="utf-8")
        loaded = S.load_session("legacy")
        assert loaded["schema_version"] == 3
        assert loaded["workflow"]["assets"]["checkpoints"] == ["sd_xl_base_1.0.safetensors"]
        assert loaded["workflow"]["assets"]["seeds"] == [42]

    def test_migration_is_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(S, "SESSIONS_DIR", tmp_path)
        state = {
            "loaded_path": "x.json",
            "format": "api",
            "base_workflow": {},
            "current_workflow": _api_workflow(),
            "history": [],
        }
        S.save_session("v3sess", workflow_state=state)
        first = S.load_session("v3sess")
        # a second load of an already-v3 session must not change the assets
        second = S.load_session("v3sess")
        assert first["workflow"]["assets"] == second["workflow"]["assets"]
        assert second["schema_version"] == 3
