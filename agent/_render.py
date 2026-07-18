"""Pure, deterministic terminal-render helpers for compact status glyphs.

These functions turn numeric series into small, always-legible strings —
Braille/eighth-block sparklines, a VRAM usage bar, and a per-step timing
line. They are stdlib-only, side-effect-free, and inert: nothing in the
agent imports or dispatches them yet. Same input always yields the same
output (He2025 determinism ethos — no wall-clock, no randomness).
"""

import math

# Braille cell dot bit values (offset from U+2800), addressed bottom -> top so
# a column of height h lights the lowest h dots. Layout per cell:
#   1 4
#   2 5
#   3 6
#   7 8
_BRAILLE_LEFT = (0x40, 0x04, 0x02, 0x01)   # dots 7,3,2,1 (bottom -> top)
_BRAILLE_RIGHT = (0x80, 0x20, 0x10, 0x08)  # dots 8,6,5,4 (bottom -> top)

_BLOCKS = "▁▂▃▄▅▆▇█"  # eighth blocks, 8 legible levels


def _finite(values: list[float]) -> list[float]:
    """Return only the finite numeric entries, dropping None/NaN/Inf/non-numbers."""
    out: list[float] = []
    for v in values:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(f) or math.isinf(f):
            continue
        out.append(f)
    return out


def _levels(values: list[float], levels: int) -> list[int]:
    """Normalize a finite series to integer bucket indices in 0..levels-1.

    All-equal input maps to a mid bucket (no divide-by-zero). Negative values
    are handled by ranging against the series min, so the lowest value is 0.
    """
    lo = min(values)
    hi = max(values)
    span = hi - lo
    out: list[int] = []
    for v in values:
        frac = 0.5 if span == 0 else (v - lo) / span
        out.append(int(frac * (levels - 1) + 0.5))
    return out


def _resample(values: list[float], n: int) -> list[float]:
    """Nearest-neighbor resample to exactly n points (deterministic)."""
    m = len(values)
    if m == 0 or n <= 0:
        return []
    if m == n:
        return list(values)
    return [values[min(m - 1, int(i * m / n))] for i in range(n)]


def _braille_column(height: int, is_left: bool) -> int:
    """Bitmask lighting the bottom `height` dots of one Braille column."""
    dots = _BRAILLE_LEFT if is_left else _BRAILLE_RIGHT
    mask = 0
    for k in range(height):
        mask |= dots[k]
    return mask


def braille_sparkline(values: list[float], width: int | None = None) -> str:
    """Render a dense Braille sparkline (2 dot-columns per char, 4 rows).

    Each column encodes one value as a height of 1..4 lit dots. When `width`
    is given the series is resampled to 2*width points so the result is exactly
    `width` characters; otherwise it is ceil(len/2) characters. None/NaN/Inf
    entries are filtered; an empty (or all-invalid) series returns "".
    """
    vals = _finite(values)
    if not vals:
        return ""
    if width is not None:
        width = max(1, int(width))
        vals = _resample(vals, 2 * width)
    heights = [idx + 1 for idx in _levels(vals, 4)]  # 1..4
    chars: list[str] = []
    for i in range(0, len(heights), 2):
        left = heights[i]
        right = heights[i + 1] if i + 1 < len(heights) else 0
        code = 0x2800 | _braille_column(left, True) | _braille_column(right, False)
        chars.append(chr(code))
    return "".join(chars)


def block_sparkline(values: list[float]) -> str:
    """Render an eighth-block sparkline (▁▂▃▄▅▆▇█), one char per value.

    Values are normalized to 8 levels against the series min/max; all-equal
    input renders a flat mid-level line. None/NaN/Inf entries are filtered;
    an empty (or all-invalid) series returns "".
    """
    vals = _finite(values)
    if not vals:
        return ""
    return "".join(_BLOCKS[i] for i in _levels(vals, 8))


def vram_bar(used_gb: float, total_gb: float, width: int = 20) -> str:
    """Render a [#####-----] usage bar with a "used/total GB" label.

    `width` is the cell count, clamped to >= 1. Fill fraction is clamped to
    0..1, so negative `used_gb`, over-budget usage, and a non-positive
    `total_gb` all degrade sanely instead of raising.
    """
    width = max(1, int(width))
    if total_gb <= 0:
        frac = 0.0
    else:
        frac = used_gb / total_gb
    frac = min(1.0, max(0.0, frac))
    filled = min(width, max(0, int(frac * width + 0.5)))
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {used_gb:.1f}/{total_gb:.1f} GB"


def format_step_times(elapsed_s: list[float]) -> str:
    """Summarize per-step elapsed seconds as "N steps · X.XX s/it avg · Y.Y s total".

    None/NaN/Inf entries are filtered and negative durations are clamped to 0.
    An empty (or all-invalid) series returns "".
    """
    vals = [max(0.0, v) for v in _finite(elapsed_s)]
    if not vals:
        return ""
    n = len(vals)
    total = sum(vals)
    avg = total / n
    return f"{n} steps · {avg:.2f} s/it avg · {total:.1f} s total"
