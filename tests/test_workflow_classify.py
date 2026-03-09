"""Tests for workflow pattern classification."""

import json

import pytest

from agent.tools.workflow_parse import (
    _build_summary,
    _classify_pattern,
    _extract_api_format,
    _trace_connections,
    handle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_workflow_from_list(node_specs):
    """Build a minimal API-format workflow from a list of (class_type, inputs) tuples."""
    wf = {}
    for i, (class_type, inputs) in enumerate(node_specs, 1):
        wf[str(i)] = {"class_type": class_type, "inputs": inputs or {}}
    return wf


# ---------------------------------------------------------------------------
# Standard txt2img base
# ---------------------------------------------------------------------------

_TXT2IMG_NODES = [
    ("CheckpointLoaderSimple", {"ckpt_name": "sd15.safetensors"}),
    ("CLIPTextEncode", {"text": "a cat", "clip": ["1", 1]}),
    ("EmptyLatentImage", {"width": 512, "height": 512, "batch_size": 1}),
    ("KSampler", {
        "model": ["1", 0],
        "positive": ["2", 0],
        "latent_image": ["3", 0],
        "steps": 20,
        "cfg": 7.0,
    }),
    ("VAEDecode", {"samples": ["4", 0], "vae": ["1", 2]}),
    ("SaveImage", {"images": ["5", 0], "filename_prefix": "out"}),
]


# ---------------------------------------------------------------------------
# TestClassifyPattern
# ---------------------------------------------------------------------------

class TestClassifyPattern:
    def test_classify_txt2img(self):
        """Standard txt2img pipeline is detected."""
        wf = _make_workflow_from_list(_TXT2IMG_NODES)
        result = _classify_pattern(wf)
        assert result["base_pattern"] == "txt2img"

    def test_classify_img2img(self):
        """img2img pipeline: LoadImage + VAEEncode + sampler + loader."""
        nodes = [
            ("CheckpointLoaderSimple", {"ckpt_name": "sd15.safetensors"}),
            ("LoadImage", {"image": "input.png"}),
            ("VAEEncode", {"pixels": ["2", 0], "vae": ["1", 2]}),
            ("KSampler", {
                "model": ["1", 0],
                "latent_image": ["3", 0],
                "steps": 20,
            }),
            ("VAEDecode", {"samples": ["4", 0], "vae": ["1", 2]}),
            ("SaveImage", {"images": ["5", 0]}),
        ]
        wf = _make_workflow_from_list(nodes)
        result = _classify_pattern(wf)
        assert result["base_pattern"] == "img2img"

    def test_classify_controlnet_modifier(self):
        """txt2img + ControlNetApply is detected as txt2img with controlnet modifier."""
        nodes = _TXT2IMG_NODES + [
            ("ControlNetApply", {"conditioning": ["2", 0]}),
        ]
        wf = _make_workflow_from_list(nodes)
        result = _classify_pattern(wf)
        assert result["base_pattern"] == "txt2img"
        assert "controlnet" in result["modifiers"]

    def test_classify_upscale_modifier(self):
        """txt2img + upscale nodes detected as modifiers."""
        nodes = _TXT2IMG_NODES + [
            ("UpscaleModelLoader", {"model_name": "4x_ultrasharp"}),
            ("ImageUpscaleWithModel", {
                "upscale_model": ["7", 0],
                "image": ["5", 0],
            }),
        ]
        wf = _make_workflow_from_list(nodes)
        result = _classify_pattern(wf)
        assert result["base_pattern"] == "txt2img"
        assert "upscale" in result["modifiers"]

    def test_classify_lora_modifier(self):
        """txt2img + LoraLoader detected as lora modifier."""
        nodes = _TXT2IMG_NODES + [
            ("LoraLoader", {"lora_name": "detail.safetensors"}),
        ]
        wf = _make_workflow_from_list(nodes)
        result = _classify_pattern(wf)
        assert result["base_pattern"] == "txt2img"
        assert "lora" in result["modifiers"]

    def test_classify_video(self):
        """VHS_VideoCombine + sampler + loader detects video pattern."""
        nodes = [
            ("CheckpointLoaderSimple", {"ckpt_name": "svd.safetensors"}),
            ("KSampler", {"model": ["1", 0], "steps": 20}),
            ("VHS_VideoCombine", {"images": ["2", 0]}),
        ]
        wf = _make_workflow_from_list(nodes)
        result = _classify_pattern(wf)
        assert "video" in result["all_patterns"]

    def test_classify_empty_workflow(self):
        """Empty dict returns base_pattern 'unknown'."""
        result = _classify_pattern({})
        assert result["base_pattern"] == "unknown"

    def test_classify_unknown_nodes(self):
        """Only custom nodes + KSampler + checkpoint returns 'custom'."""
        nodes = [
            ("CheckpointLoaderSimple", {"ckpt_name": "sd15.safetensors"}),
            ("KSampler", {"model": ["1", 0], "steps": 20}),
            ("MyCustomPostProcess", {"image": ["2", 0]}),
        ]
        wf = _make_workflow_from_list(nodes)
        result = _classify_pattern(wf)
        assert result["base_pattern"] == "custom"

    def test_classify_tool_handler(self, tmp_path):
        """classify_workflow tool handler returns JSON with classification fields."""
        wf = _make_workflow_from_list(_TXT2IMG_NODES)
        wf_path = tmp_path / "classify_test.json"
        wf_path.write_text(json.dumps(wf), encoding="utf-8")

        result = json.loads(handle("classify_workflow", {"path": str(wf_path)}))
        assert "base_pattern" in result
        assert "modifiers" in result
        assert "all_patterns" in result
        assert "description" in result
        assert result["base_pattern"] == "txt2img"

    def test_build_summary_includes_pattern(self):
        """_build_summary with classification dict shows 'Pipeline:' text."""
        wf = _make_workflow_from_list(_TXT2IMG_NODES)
        classification = _classify_pattern(wf)
        connections = _trace_connections(wf)
        summary = _build_summary(wf, connections, "api", classification)
        assert "Pipeline:" in summary

    def test_classify_compound_description(self):
        """txt2img + controlnet + lora produces description with 'with' for modifiers."""
        nodes = _TXT2IMG_NODES + [
            ("ControlNetApply", {"conditioning": ["2", 0]}),
            ("LoraLoader", {"lora_name": "detail.safetensors"}),
        ]
        wf = _make_workflow_from_list(nodes)
        result = _classify_pattern(wf)
        assert "with" in result["description"].lower()
        assert result["base_pattern"] == "txt2img"
        assert len(result["modifiers"]) >= 2
