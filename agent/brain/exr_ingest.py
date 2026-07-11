"""Linear EXR ingestion for the vision tools (hardening doc 3.7).

Pillow has no EXR codec, so render passes never reached the vision loop.
This module converts a linear EXR beauty pass into display-referred sRGB
PNG bytes that the Vision API accepts.

MVP caveats (honest): values are clipped to 1.0 before the sRGB encode, so
highlights above 1.0 burn to white — there is no filmic tonemap. An OCIO
show-config transform is the named stretch (ledger lead); the ``exposure``
parameter is the manual escape hatch until then.
"""

import io
import logging

log = logging.getLogger(__name__)

try:
    import numpy as np
    import OpenEXR
    _HAS_EXR = True
except ImportError:
    _HAS_EXR = False

# ACES AP1 (ACEScg) primaries + D60 white as flat xy pairs — the header's
# "chromaticities" attribute reads back as a tuple of 8 floats (probed on
# OpenEXR 3.4): (red.x, red.y, green.x, green.y, blue.x, blue.y, white.x, white.y).
_AP1_XY = (0.713, 0.293, 0.165, 0.830, 0.128, 0.044, 0.32168, 0.33767)
# Published AP1 -> linear Rec.709 matrix (Bradford-adapted D60 -> D65).
_AP1_TO_REC709 = (
    (1.70505, -0.62179, -0.08326),
    (-0.13026, 1.14080, -0.01055),
    (-0.02400, -0.12897, 1.15297),
)


def _is_ap1(chromaticities) -> bool:
    """True when header chromaticities match ACES AP1 within 1e-3 per coordinate."""
    try:
        vals = [float(v) for v in chromaticities]
    except (TypeError, ValueError):
        return False
    if len(vals) != 8:
        return False
    return all(abs(a - b) <= 1e-3 for a, b in zip(vals, _AP1_XY))


def _extract_rgb(channels: dict):
    """Assemble an (H, W, 3) float32 array from an EXR ``channels()`` dict.

    Default readers group R/G/B(/A) into one "RGB"/"RGBA" key; some writers/
    readers keep separate 2-D "R", "G", "B" channels — handle both. Anything
    else is a data/utility pass the vision loop cannot judge.
    """
    for key in ("RGB", "RGBA"):
        if key in channels:
            return np.asarray(channels[key].pixels)[..., :3].astype(np.float32)
    if all(c in channels for c in ("R", "G", "B")):
        return np.stack(
            [np.asarray(channels[c].pixels, dtype=np.float32) for c in ("R", "G", "B")],
            axis=-1,
        )
    found = ", ".join(sorted(channels))
    raise ValueError(
        f"This is a data/utility pass (channels: {found}) — "
        "vision analysis needs a beauty/display pass."
    )


def exr_to_display_png(path: str, exposure: float = 0.0) -> bytes:
    """Convert a linear EXR beauty pass to display-referred sRGB PNG bytes.

    Pipeline: exposure multiply (2**exposure) -> AP1->Rec.709 primary
    conversion when the header chromaticities say ACEScg (absent or other
    primaries skip it — the EXR spec default is already Rec.709) -> clip to
    [0, 1] -> sRGB EOTF -> 8-bit PNG.

    Caveats: the clip burns highlights above 1.0 to white — no filmic
    tonemap. MVP per hardening doc 3.7; an OCIO show-config transform is the
    named stretch (ledger lead), ``exposure`` is the manual escape hatch.
    """
    if not _HAS_EXR:
        raise ValueError(
            "EXR support needs the optional dependency — pip install 'comfy-cozy[exr]'"
        )
    from PIL import Image

    with OpenEXR.File(path) as f:  # default part; f.parts exists for multi-part
        rgb = _extract_rgb(f.channels())
        # Probed on OpenEXR 3.4: f.header() is live-bound to the open file —
        # after the context closes, its attributes vanish. Decide here.
        is_ap1 = _is_ap1(f.header().get("chromaticities"))

    rgb = rgb * np.float32(2.0 ** exposure)
    if is_ap1:
        rgb = rgb @ np.asarray(_AP1_TO_REC709, dtype=np.float32).T
    rgb = np.clip(rgb, 0.0, 1.0)
    srgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * rgb ** (1.0 / 2.4) - 0.055)
    buf = io.BytesIO()
    Image.fromarray((srgb * 255.0 + 0.5).astype(np.uint8), mode="RGB").save(buf, format="PNG")
    return buf.getvalue()
