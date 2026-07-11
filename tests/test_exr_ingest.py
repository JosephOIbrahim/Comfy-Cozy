"""Tests for agent/brain/exr_ingest.py — linear EXR ingestion (hardening doc 3.7).

Skips everywhere the [exr] extra is absent; CI installs it, so these RUN there.
"""

import base64
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

OpenEXR = pytest.importorskip("OpenEXR")
np = pytest.importorskip("numpy")

from PIL import Image

from agent.brain import handle
from agent.brain.exr_ingest import _extract_rgb, exr_to_display_png
from agent.llm import LLMResponse, TextBlock

_HEADER = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}


def _write_exr(path, channels, header=None):
    OpenEXR.File(dict(header or _HEADER), channels).write(str(path))


def _gradient_exr(path):
    """2x3 linear ramp: columns 0.0 / 0.5 / 1.0 across all RGB channels."""
    arr = np.zeros((2, 3, 3), dtype=np.float32)
    arr[:, 1, :] = 0.5
    arr[:, 2, :] = 1.0
    _write_exr(path, {"RGB": OpenEXR.Channel(arr)})


def _srgb_encode(x: float) -> float:
    return x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055


# Mirrors tests/test_brain_vision.py's provider-mock harness.
def _patch_provider(response_text: str):
    mock_provider = MagicMock()
    mock_provider.create.return_value = LLMResponse(
        content=[TextBlock(text=response_text)],
        stop_reason="end_turn",
        model="test-model",
    )
    return patch("agent.brain.vision.get_provider", return_value=mock_provider)


class TestExrToDisplayPng:
    def test_linear_gradient_srgb_math(self, tmp_path):
        """(a) 0.0 -> 0, 1.0 -> 255, 0.5 -> the sRGB EOTF value (computed in-test)."""
        src = tmp_path / "ramp.exr"
        _gradient_exr(src)
        img = Image.open(io.BytesIO(exr_to_display_png(str(src))))
        assert img.size == (3, 2)  # (W, H)
        assert img.getpixel((0, 0)) == (0, 0, 0)
        assert img.getpixel((2, 0)) == (255, 255, 255)
        expected_half = round(255 * _srgb_encode(0.5))
        for channel in img.getpixel((1, 0)):
            assert abs(channel - expected_half) <= 1

    def test_overbright_clips_to_white(self, tmp_path):
        """(b) values above 1.0 burn to 255 — clip-to-1, no filmic tonemap (MVP)."""
        src = tmp_path / "hot.exr"
        _write_exr(src, {"RGB": OpenEXR.Channel(np.full((2, 2, 3), 7.5, dtype=np.float32))})
        img = Image.open(io.BytesIO(exr_to_display_png(str(src))))
        assert img.getextrema() == ((255, 255), (255, 255), (255, 255))

    def test_data_pass_rejected(self, tmp_path):
        """(c) a Z-only pass is a data image — refuse with the channel named."""
        src = tmp_path / "depth.exr"
        _write_exr(src, {"Z": OpenEXR.Channel(np.ones((2, 2), dtype=np.float32))})
        with pytest.raises(ValueError) as exc:
            exr_to_display_png(str(src))
        assert "data" in str(exc.value)
        assert "Z" in str(exc.value)

    def test_separate_rgb_channels_convert(self, tmp_path):
        """(d) an EXR written as separate R/G/B channels converts fine."""
        src = tmp_path / "sep.exr"
        plane = np.full((2, 2), 1.0, dtype=np.float32)
        _write_exr(src, {
            "R": OpenEXR.Channel(plane),
            "G": OpenEXR.Channel(plane),
            "B": OpenEXR.Channel(plane),
        })
        img = Image.open(io.BytesIO(exr_to_display_png(str(src))))
        assert img.size == (2, 2)
        assert img.getpixel((0, 0)) == (255, 255, 255)

    def test_ungrouped_reader_branch_stacks_planes(self):
        """(d) cont. — default readers regroup R/G/B into "RGB" (probed on
        OpenEXR 3.4), so exercise the ungrouped 2-D-planes branch directly."""
        from types import SimpleNamespace

        plane = np.full((2, 2), 0.5, dtype=np.float32)
        rgb = _extract_rgb({c: SimpleNamespace(pixels=plane) for c in ("R", "G", "B")})
        assert rgb.shape == (2, 2, 3)
        assert rgb.dtype == np.float32

    def test_exposure_escape_hatch(self, tmp_path):
        """exposure is in stops: 0.25 at +2 reaches 1.0 -> pure white."""
        src = tmp_path / "dim.exr"
        _write_exr(src, {"RGB": OpenEXR.Channel(np.full((2, 2, 3), 0.25, dtype=np.float32))})
        img = Image.open(io.BytesIO(exr_to_display_png(str(src), exposure=2.0)))
        assert img.getpixel((0, 0)) == (255, 255, 255)

    def test_ap1_chromaticities_apply_matrix(self, tmp_path):
        """ACEScg header chromaticities trigger the AP1 -> Rec.709 matrix."""
        header = dict(_HEADER)
        header["chromaticities"] = (0.713, 0.293, 0.165, 0.830, 0.128, 0.044, 0.32168, 0.33767)
        src = tmp_path / "acescg.exr"
        lin = (0.2, 0.5, 0.1)
        arr = np.tile(np.asarray(lin, dtype=np.float32), (2, 2, 1))
        _write_exr(src, {"RGB": OpenEXR.Channel(arr)}, header=header)

        matrix = ((1.70505, -0.62179, -0.08326),
                  (-0.13026, 1.14080, -0.01055),
                  (-0.02400, -0.12897, 1.15297))
        expected = tuple(
            round(255 * _srgb_encode(min(1.0, max(0.0, sum(r * v for r, v in zip(row, lin))))))
            for row in matrix
        )
        img = Image.open(io.BytesIO(exr_to_display_png(str(src))))
        for got, want in zip(img.getpixel((0, 0)), expected):
            assert abs(got - want) <= 2

    def test_missing_dependency_hint(self, tmp_path, monkeypatch):
        """(h) without the optional dependency the error names the extra."""
        from agent.brain import exr_ingest

        monkeypatch.setattr(exr_ingest, "_HAS_EXR", False)
        with pytest.raises(ValueError, match=r"comfy-cozy\[exr\]"):
            exr_to_display_png(str(tmp_path / "any.exr"))


class TestVisionIntegration:
    def test_analyze_image_exr_end_to_end(self, tmp_path):
        """(e) analyze_image on an EXR ships a real PNG ImageBlock to the API."""
        src = tmp_path / "beauty.exr"
        _gradient_exr(src)
        with _patch_provider(json.dumps({"quality_score": 0.9})) as mock_get:
            result = json.loads(handle("analyze_image", {"image_path": str(src)}))

        assert "error" not in result
        kwargs = mock_get.return_value.create.call_args.kwargs
        image_block = kwargs["messages"][0]["content"][0]
        assert image_block.media_type == "image/png"
        assert base64.b64decode(image_block.data)[:8] == b"\x89PNG\r\n\x1a\n"

    def test_unknown_suffix_rejected_before_api(self, tmp_path):
        """(f) unsupported suffixes fail friendly, never reaching the provider."""
        junk = tmp_path / "render.tiff"
        junk.write_bytes(b"II*\x00junkjunkjunk")
        with _patch_provider("{}") as mock_get:
            result = json.loads(handle("analyze_image", {"image_path": str(junk)}))

        assert "error" in result
        assert "Unsupported image format" in result["error"]
        assert ".tiff" in result["error"]
        mock_get.return_value.create.assert_not_called()

    def test_hash_compare_same_exr(self, tmp_path):
        """(g) hash_compare_images accepts EXR; same file twice is identical."""
        src = tmp_path / "beauty.exr"
        _gradient_exr(src)
        result = json.loads(handle("hash_compare_images", {
            "image_a": str(src),
            "image_b": str(src),
        }))
        assert "error" not in result
        assert result["verdict"] == "identical"
        assert result["hash_similarity"] == 1.0


class TestVisionCacheSandbox:
    def test_outside_sandbox_not_read(self, monkeypatch):
        """(i) analyze_image_cached must sandbox-validate BEFORE reading bytes."""
        from agent.tools import vision_cache

        reads = []
        original = Path.read_bytes

        def spy(self):
            reads.append(str(self))
            return original(self)

        monkeypatch.setattr(Path, "read_bytes", spy)
        result = json.loads(vision_cache.handle(
            "analyze_image_cached", {"image_path": "/etc/passwd"}))
        assert "error" in result
        assert "denied" in result["error"].lower()
        assert reads == []
