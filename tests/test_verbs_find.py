"""Tests for the FIND verb engine (agent/verbs/find.py) — all filesystem via
tmp_path, all HTTP-adjacent seams mocked. No real ComfyUI needed."""

import json
from unittest.mock import patch

import pytest

from agent.tools import comfy_inspect
from agent.verbs import find


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

    (models / "controlnet").mkdir()  # empty dir — no model files
    return models


@pytest.fixture
def fake_custom_nodes(tmp_path):
    """Fake Custom_Nodes directory with two packs."""
    cn = tmp_path / "Custom_Nodes"
    cn.mkdir()

    pack1 = cn / "comfyui-impact-pack"
    pack1.mkdir()
    (pack1 / "__init__.py").write_text("NODE_CLASS_MAPPINGS = {}\n")
    (pack1 / "requirements.txt").write_text("numpy\n")

    pack2 = cn / "some-utils"
    pack2.mkdir()
    (pack2 / "helpers.py").write_text("import os\n")
    return cn


@pytest.fixture
def sd15_workflow():
    """Minimal API-format workflow referencing one installed SD1.5 checkpoint."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "dreamshaper_v8.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {"seed": 42, "model": ["1", 0]},
        },
    }


# ---------------------------------------------------------------------------
# Models report
# ---------------------------------------------------------------------------


class TestBuildModelsReport:
    def test_groups_by_directory(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report(use_session_workflow=False)
        types = [g["model_type"] for g in report["groups"]]
        assert types == ["checkpoints", "loras"]  # empty controlnet excluded
        ckpts = report["groups"][0]
        assert ckpts["count"] == 3

    def test_family_and_status_tags(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report(use_session_workflow=False)
        ckpts = {m["name"]: m for m in report["groups"][0]["models"]}
        assert ckpts["dreamshaper_v8.safetensors"]["family"] == "sd15"
        assert ckpts["dreamshaper_v8.safetensors"]["glyph"] == find.GLYPH_OK
        assert ckpts["sdxl_base_1.0.safetensors"]["family"] == "sdxl"
        broken = ckpts["broken_download.safetensors"]
        assert broken["status"] == "attention"
        assert broken["glyph"] == find.GLYPH_ATTENTION
        assert "zero-byte" in broken["note"]

    def test_single_type_filter(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report(model_type="loras", use_session_workflow=False)
        assert len(report["groups"]) == 1
        assert report["groups"][0]["model_type"] == "loras"

    def test_unknown_type_notes_in_human_words(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report(
                model_type="motion_models", use_session_workflow=False
            )
        assert report["groups"] == []
        assert "motion_models" in report["note"]
        assert "checkpoints" in report["note"]  # lists what does exist

    def test_missing_models_dir_never_crashes(self, tmp_path):
        with patch.object(comfy_inspect, "MODELS_DIR", tmp_path / "nope"):
            report = find.build_models_report(use_session_workflow=False)
        assert report["groups"] == []
        assert "COMFYUI_DATABASE" in report["note"]

    def test_workflow_reference_found(self, fake_models, sd15_workflow):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report(workflow=sd15_workflow)
        wf = report["workflow"]
        assert wf["checked"] is True
        assert len(wf["references"]) == 1
        ref = wf["references"][0]
        assert ref["status"] == "ok"
        assert ref["model_type"] == "checkpoints"

    def test_workflow_reference_missing(self, fake_models, sd15_workflow):
        sd15_workflow["1"]["inputs"]["ckpt_name"] = "not_on_disk.safetensors"
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report(workflow=sd15_workflow)
        ref = report["workflow"]["references"][0]
        assert ref["status"] == "missing"
        assert ref["glyph"] == find.GLYPH_MISSING

    def test_workflow_family_mismatch_flagged(self, fake_models, sd15_workflow):
        sd15_workflow["3"] = {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "style_sdxl.safetensors"},
        }
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report(workflow=sd15_workflow)
        refs = {r["name"]: r for r in report["workflow"]["references"]}
        assert refs["dreamshaper_v8.safetensors"]["status"] == "ok"
        mismatch = refs["style_sdxl.safetensors"]
        assert mismatch["status"] == "attention"
        assert "mismatch" in mismatch["note"]

    def test_no_workflow_loaded_notes_it(self, fake_models):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report()  # session state is reset by conftest
        assert report["workflow"]["checked"] is False
        assert "No workflow loaded" in report["workflow"]["note"]


class TestExtractModelReferences:
    def test_dedupes_and_sorts(self, sd15_workflow):
        sd15_workflow["3"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "dreamshaper_v8.safetensors"},
        }
        refs = find.extract_model_references(sd15_workflow)
        assert [r["name"] for r in refs] == ["dreamshaper_v8.safetensors"]

    def test_ignores_non_model_strings_and_connections(self, sd15_workflow):
        refs = find.extract_model_references(sd15_workflow)
        assert len(refs) == 1  # seed int and ["1", 0] connection ignored


# ---------------------------------------------------------------------------
# Nodes report
# ---------------------------------------------------------------------------


class TestBuildNodesReport:
    def test_lists_installed_packs(self, fake_custom_nodes):
        with patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes):
            report = find.build_nodes_report(check_workflow=False)
        assert report["count"] == 2
        names = [p["name"] for p in report["packs"]]
        assert names == ["comfyui-impact-pack", "some-utils"]
        assert all(p["glyph"] == find.GLYPH_OK for p in report["packs"])

    def test_missing_dir_never_crashes(self, tmp_path):
        with patch.object(comfy_inspect, "CUSTOM_NODES_DIR", tmp_path / "nope"):
            report = find.build_nodes_report(check_workflow=False)
        assert report["packs"] == []
        assert "COMFYUI_DATABASE" in report["note"]

    def test_comfyui_down_degrades_in_human_words(self, fake_custom_nodes):
        down = json.dumps(
            {
                "error": "ComfyUI not reachable. Start ComfyUI to check node availability.",
            }
        )
        with (
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch("agent.tools.comfy_discover.handle", return_value=down),
        ):
            report = find.build_nodes_report()
        assert report["count"] == 2  # local scan still succeeded
        wf = report["workflow"]
        assert wf["checked"] is False
        assert "ComfyUI is not running" in wf["note"]

    def test_no_workflow_loaded_notes_it(self, fake_custom_nodes):
        no_wf = json.dumps(
            {
                "error": (
                    "No workflow loaded. Either provide a 'path' or load one "
                    "with apply_workflow_patch first."
                ),
            }
        )
        with (
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch("agent.tools.comfy_discover.handle", return_value=no_wf),
        ):
            report = find.build_nodes_report()
        assert report["workflow"]["checked"] is False
        assert "No workflow loaded" in report["workflow"]["note"]

    def test_missing_nodes_marked(self, fake_custom_nodes):
        missing = json.dumps(
            {
                "status": "missing_nodes",
                "total_node_types": 5,
                "installed_count": 4,
                "missing_count": 1,
                "missing_nodes": [
                    {
                        "node_type": "ImpactWildcardProcessor",
                        "pack_title": "Impact Pack",
                        "pack_url": "https://github.com/ltdrdata/ComfyUI-Impact-Pack",
                        "pack_installed": False,
                    }
                ],
                "packs_to_install": [],
            }
        )
        with (
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch("agent.tools.comfy_discover.handle", return_value=missing) as mocked,
        ):
            report = find.build_nodes_report(workflow_path="wf.json")
        mocked.assert_called_once_with("find_missing_nodes", {"path": "wf.json"})
        wf = report["workflow"]
        assert wf["checked"] is True
        assert wf["missing"][0]["glyph"] == find.GLYPH_MISSING
        assert wf["missing"][0]["node_type"] == "ImpactWildcardProcessor"
        assert "missing" in wf["note"]

    def test_all_installed(self, fake_custom_nodes):
        ok = json.dumps(
            {
                "status": "all_installed",
                "total_node_types": 5,
                "message": "All node types in this workflow are available.",
            }
        )
        with (
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch("agent.tools.comfy_discover.handle", return_value=ok),
        ):
            report = find.build_nodes_report()
        assert report["workflow"]["checked"] is True
        assert report["workflow"]["missing"] == []


# ---------------------------------------------------------------------------
# Command palette
# ---------------------------------------------------------------------------


class TestCommandPalette:
    def test_empty_query_returns_full_palette(self):
        entries = find.command_palette("", limit=50)
        commands = [e["command"] for e in entries]
        assert "cozy models list" in commands
        assert "cozy nodes list" in commands
        assert len(commands) == len(find.PALETTE)

    def test_exact_word_ranks_first(self):
        entries = find.command_palette("models")
        assert entries[0]["command"] == "cozy models list"

    def test_fuzzy_typo_still_finds(self):
        entries = find.command_palette("modl")
        assert any(e["command"] == "cozy models list" for e in entries)

    def test_keyword_match(self):
        entries = find.command_palette("loras")
        assert entries[0]["command"] == "cozy models list"

    def test_garbage_returns_empty(self):
        assert find.command_palette("zzqqxx") == []

    def test_deterministic_ordering(self):
        assert find.command_palette("list") == find.command_palette("list")

    def test_limit_respected(self):
        assert len(find.command_palette("", limit=3)) == 3


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


class TestRenderers:
    def test_models_render_has_glyphs_and_groups(self, fake_models, sd15_workflow):
        with patch.object(comfy_inspect, "MODELS_DIR", fake_models):
            report = find.build_models_report(workflow=sd15_workflow)
        text = find.render_models_report(report)
        assert "checkpoints (3)" in text
        assert find.GLYPH_OK in text
        assert find.GLYPH_ATTENTION in text
        assert "Workflow models:" in text

    def test_nodes_render_lists_packs_and_note(self, fake_custom_nodes):
        down = json.dumps({"error": "ComfyUI not reachable."})
        with (
            patch.object(comfy_inspect, "CUSTOM_NODES_DIR", fake_custom_nodes),
            patch("agent.tools.comfy_discover.handle", return_value=down),
        ):
            report = find.build_nodes_report()
        text = find.render_nodes_report(report)
        assert "comfyui-impact-pack" in text
        assert "ComfyUI is not running" in text

    def test_palette_render_empty_suggests_commands(self):
        text = find.render_palette([])
        assert "cozy models list" in text

    def test_palette_render_aligned(self):
        text = find.render_palette(find.command_palette("list"))
        assert "cozy" in text
