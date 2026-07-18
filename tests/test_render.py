"""Tests for agent/_render.py — pure terminal-render helpers.

Mirrors tests/test_util.py: class-per-behavior grouping, one-line docstrings,
plain asserts, pytest only, no ComfyUI/network. Covers each function's happy
path plus every declared edge case (empty, single, all-equal, None/NaN, width
clamp, negative), and asserts deterministic output.
"""

from agent._render import (
    block_sparkline,
    braille_sparkline,
    format_step_times,
    vram_bar,
)


class TestBrailleSparkline:
    """braille_sparkline maps a series to Braille dots (U+2800..U+28FF)."""

    def test_empty_returns_empty(self):
        """Empty input returns an empty string, no crash."""
        assert braille_sparkline([]) == ""

    def test_single_value(self):
        """A single value renders one non-empty Braille char."""
        out = braille_sparkline([5.0])
        assert len(out) == 1
        assert 0x2800 <= ord(out) <= 0x28FF

    def test_all_chars_in_braille_range(self):
        """Every rendered char lands in the Braille Unicode block."""
        out = braille_sparkline([1.0, 3.0, 2.0, 8.0, 4.0])
        assert all(0x2800 <= ord(c) <= 0x28FF for c in out)

    def test_char_count_without_width(self):
        """Without width, output is ceil(len/2) chars (2 values per char)."""
        assert len(braille_sparkline([1.0, 2.0, 3.0, 4.0])) == 2
        assert len(braille_sparkline([1.0, 2.0, 3.0])) == 2

    def test_width_sets_exact_char_count(self):
        """A given width produces exactly that many chars via resampling."""
        assert len(braille_sparkline([1.0, 2.0, 3.0, 4.0, 5.0], width=8)) == 8
        assert len(braille_sparkline([1.0, 2.0], width=3)) == 3

    def test_width_clamped_to_at_least_one(self):
        """width <= 0 clamps to 1 char instead of producing nothing/crashing."""
        assert len(braille_sparkline([1.0, 2.0, 3.0], width=0)) == 1
        assert len(braille_sparkline([1.0, 2.0, 3.0], width=-5)) == 1

    def test_all_equal_no_crash(self):
        """All-equal input renders a flat line without divide-by-zero."""
        out = braille_sparkline([2.0, 2.0, 2.0, 2.0])
        assert len(out) == 2
        assert all(0x2800 <= ord(c) <= 0x28FF for c in out)

    def test_none_and_nan_filtered(self):
        """None/NaN entries are dropped before rendering."""
        clean = braille_sparkline([1.0, 2.0, 3.0, 4.0])
        mixed = braille_sparkline([1.0, None, float("nan"), 2.0, 3.0, 4.0])
        assert mixed == clean

    def test_all_invalid_returns_empty(self):
        """A series of only None/NaN returns empty string."""
        assert braille_sparkline([None, float("nan"), float("inf")]) == ""

    def test_negative_values_handled(self):
        """Negative values render sanely within the Braille range."""
        out = braille_sparkline([-5.0, -1.0, -3.0, 0.0])
        assert all(0x2800 <= ord(c) <= 0x28FF for c in out)

    def test_deterministic(self):
        """Same input yields identical output across calls."""
        data = [1.0, 4.0, 2.0, 9.0, 3.0, 7.0]
        assert braille_sparkline(data) == braille_sparkline(data)
        assert braille_sparkline(data, width=4) == braille_sparkline(data, width=4)


class TestBlockSparkline:
    """block_sparkline renders one eighth-block char per value."""

    def test_empty_returns_empty(self):
        """Empty input returns empty string."""
        assert block_sparkline([]) == ""

    def test_one_char_per_value(self):
        """Output length equals the count of finite values."""
        assert len(block_sparkline([1.0, 2.0, 3.0, 4.0, 5.0])) == 5

    def test_single_value(self):
        """A single value renders exactly one block char."""
        out = block_sparkline([42.0])
        assert len(out) == 1
        assert out in "▁▂▃▄▅▆▇█"

    def test_ascending_is_monotone_nondecreasing(self):
        """An ascending series maps to non-decreasing block heights."""
        out = block_sparkline([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        blocks = "▁▂▃▄▅▆▇█"
        levels = [blocks.index(c) for c in out]
        assert levels == sorted(levels)
        assert levels[0] == 0
        assert levels[-1] == 7

    def test_min_and_max_span_full_range(self):
        """The min value uses the lowest block, the max the highest."""
        out = block_sparkline([0.0, 100.0])
        assert out[0] == "▁"
        assert out[-1] == "█"

    def test_all_equal_flat_midlevel(self):
        """All-equal input renders identical mid-level blocks, no crash."""
        out = block_sparkline([3.0, 3.0, 3.0])
        assert len(out) == 3
        assert len(set(out)) == 1
        assert out[0] in "▁▂▃▄▅▆▇█"

    def test_none_and_nan_filtered(self):
        """None/NaN entries are dropped, shortening the output."""
        assert block_sparkline([1.0, None, 2.0, float("nan"), 3.0]) == block_sparkline(
            [1.0, 2.0, 3.0]
        )

    def test_all_chars_are_blocks(self):
        """Every char is one of the eight block glyphs."""
        out = block_sparkline([5.0, 1.0, 9.0, 2.0, 7.0])
        assert all(c in "▁▂▃▄▅▆▇█" for c in out)

    def test_negative_values_handled(self):
        """Negative values normalize sanely (lowest -> lowest block)."""
        out = block_sparkline([-10.0, -5.0, 0.0])
        assert out[0] == "▁"
        assert out[-1] == "█"

    def test_deterministic(self):
        """Same input yields identical output."""
        data = [2.0, 8.0, 4.0, 1.0]
        assert block_sparkline(data) == block_sparkline(data)


class TestVramBar:
    """vram_bar renders a [#####-----] bar with a used/total GB label."""

    def test_shape_and_label(self):
        """Bar has `width` cells inside brackets and a GB label."""
        out = vram_bar(10.0, 20.0, width=20)
        assert out.startswith("[")
        assert "] " in out
        bar = out[1:out.index("]")]
        assert len(bar) == 20
        assert out.endswith("10.0/20.0 GB")

    def test_half_full(self):
        """Half usage fills half the cells."""
        out = vram_bar(10.0, 20.0, width=10)
        bar = out[1:out.index("]")]
        assert bar.count("#") == 5
        assert bar.count("-") == 5

    def test_empty_usage(self):
        """Zero used renders no filled cells."""
        bar = vram_bar(0.0, 20.0, width=10)[1:11]
        assert bar == "-" * 10

    def test_full_usage(self):
        """Full usage fills every cell."""
        bar = vram_bar(20.0, 20.0, width=10)[1:11]
        assert bar == "#" * 10

    def test_over_budget_clamped(self):
        """used > total clamps to a full bar, not overflow."""
        bar = vram_bar(30.0, 20.0, width=10)[1:11]
        assert bar == "#" * 10

    def test_negative_used_clamped(self):
        """Negative used clamps to an empty bar."""
        bar = vram_bar(-5.0, 20.0, width=10)[1:11]
        assert bar == "-" * 10

    def test_zero_total_no_crash(self):
        """Non-positive total avoids divide-by-zero and renders empty bar."""
        out = vram_bar(5.0, 0.0, width=8)
        assert out[1:9] == "-" * 8
        assert out.endswith("5.0/0.0 GB")

    def test_width_clamped_to_at_least_one(self):
        """width <= 0 clamps to a single cell."""
        assert vram_bar(1.0, 2.0, width=0)[1:2] in ("#", "-")
        assert len(vram_bar(1.0, 2.0, width=0)[1:vram_bar(1.0, 2.0, width=0).index("]")]) == 1

    def test_bar_length_always_width(self):
        """Filled + empty cells always equal width across usage levels."""
        for used in (0.0, 3.3, 7.5, 16.0, 20.0):
            bar = vram_bar(used, 20.0, width=17)
            inner = bar[1:bar.index("]")]
            assert len(inner) == 17

    def test_deterministic(self):
        """Same input yields identical output."""
        assert vram_bar(12.0, 24.0, width=15) == vram_bar(12.0, 24.0, width=15)


class TestFormatStepTimes:
    """format_step_times summarizes per-step elapsed seconds."""

    def test_empty_returns_empty(self):
        """Empty input returns empty string."""
        assert format_step_times([]) == ""

    def test_happy_path(self):
        """A series reports count, average s/it, and total seconds."""
        out = format_step_times([0.4, 0.5, 0.3])
        assert out == "3 steps · 0.40 s/it avg · 1.2 s total"

    def test_single_value(self):
        """A single step reports avg equal to total."""
        out = format_step_times([2.0])
        assert out == "1 steps · 2.00 s/it avg · 2.0 s total"

    def test_all_equal(self):
        """All-equal steps report that value as the average."""
        out = format_step_times([0.5, 0.5, 0.5, 0.5])
        assert "4 steps" in out
        assert "0.50 s/it avg" in out
        assert "2.0 s total" in out

    def test_none_and_nan_filtered(self):
        """None/NaN entries are excluded from count, avg, and total."""
        assert format_step_times([0.4, None, float("nan"), 0.6]) == format_step_times(
            [0.4, 0.6]
        )

    def test_all_invalid_returns_empty(self):
        """A series of only invalid entries returns empty string."""
        assert format_step_times([None, float("nan"), float("inf")]) == ""

    def test_negative_clamped_to_zero(self):
        """Negative durations clamp to 0 rather than skewing the total."""
        out = format_step_times([-1.0, 1.0])
        assert out == "2 steps · 0.50 s/it avg · 1.0 s total"

    def test_deterministic(self):
        """Same input yields identical output."""
        data = [0.42, 0.41, 0.43, 0.40]
        assert format_step_times(data) == format_step_times(data)
