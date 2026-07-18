"""CLI wiring tests for the Mile-3/5 verbs: run --recipe (INTEND) and doctor/stats/model search (OWN).

The engine layers (agent/verbs/{intend,own}.py) carry their own test files;
these tests pin the CLI layer only — command registration, help text,
happy-path rendering with the engines mocked, degraded paths, and exit
codes. All mocked: no ComfyUI server, no network, no API key.
"""

import io
import json
import sys
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import agent.config as config
from agent.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_sessions_dir(tmp_path, monkeypatch):
    """The recipe rail now restores/persists the CLI session sidecar (defect
    B1) — keep every test's sidecar reads and writes out of the real
    sessions directory."""
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path / "sessions")


def _flat(output: str) -> str:
    """Collapse console line-wrapping so phrase assertions survive any width."""
    return " ".join(output.split())


# ---------------------------------------------------------------------------
# Fixture-shaped results (match the engine contracts' structured dict shapes)
# ---------------------------------------------------------------------------


def _applied_recipe_result() -> dict:
    return {
        "matched": True,
        "recipe": {
            "name": "dreamier",
            "description": "Softer, more ethereal look",
            "category": "look",
            "requires_workflow": True,
            "total_steps": 4,
        },
        "available": ["dreamier", "sharper", "faster"],
        "applied": True,
        "steps_run": 2,
        "fall_through": False,
        "changes": [
            {
                "node_id": "3",
                "class_type": "KSampler",
                "param": "cfg",
                "old": 8.0,
                "new": 6.0,
            }
        ],
        "nodes_added": [],
        "message": "Applied dreamier.",
        "error": None,
    }


def _fall_through_result(message: str) -> dict:
    return {
        "matched": True,
        "recipe": {
            "name": "dreamier",
            "description": "Softer, more ethereal look",
            "category": "look",
            "requires_workflow": True,
        },
        "available": ["dreamier", "sharper", "faster"],
        "applied": False,
        "steps_run": 0,
        "fall_through": True,
        "changes": [],
        "nodes_added": [],
        "message": message,
        "error": None,
    }


_VALIDATION_OK = json.dumps(
    {
        "valid": True,
        "node_count": 7,
        "errors": [],
        "warnings": [],
        "message": "Workflow looks ready to execute.",
    }
)

_VALIDATION_BAD = json.dumps(
    {
        "valid": False,
        "errors": ["Node [3] KSampler: missing required input 'seed'."],
        "warnings": [],
        "message": "Fix errors before executing.",
    }
)

_EXEC_COMPLETE = json.dumps(
    {
        "status": "complete",
        "prompt_id": "abc-123",
        "total_time_s": 3.0,
        "outputs": [{"type": "image", "filename": "out_00001.png", "subfolder": ""}],
        "node_timing": [{"node_id": "3", "class_type": "KSampler", "duration_s": 2.1}],
        "slowest_node": {"node_id": "3", "class_type": "KSampler", "duration_s": 2.1},
        "progress_events": 0,
        "progress_log": [],
        "monitoring": "websocket",
    }
)

_API_DOWN = json.dumps({"error": "ComfyUI is not reachable at http://127.0.0.1:8188"})


def _doctor(ok: bool) -> dict:
    checks = [
        {
            "name": "comfyui",
            "ok": True,
            "glyph": "✓",
            "note": "ComfyUI is up at http://127.0.0.1:8188.",
            "fix_hint": None,
        },
        {
            "name": "models_folder",
            "ok": ok,
            "glyph": "✓" if ok else "✗",
            "note": (
                "Models folder found." if ok else "No models folder at X:/COMFYUI_Database/models."
            ),
            "fix_hint": None if ok else "Check COMFYUI_DATABASE in your .env.",
        },
    ]
    problems = [c for c in checks if not c["ok"]]
    return {
        "checks": checks,
        "ok": not problems,
        "summary": (
            "Everything looks healthy."
            if not problems
            else f"{len(problems)} of {len(checks)} checks need attention."
        ),
    }


def _stats(gpu_up: bool) -> dict:
    return {
        "models": {
            "source": "X:/COMFYUI_Database/models",
            "by_type": [
                {
                    "model_type": "checkpoints",
                    "count": 2,
                    "total_size_bytes": 4294967296,
                    "total_size": "4.0 GB",
                }
            ],
            "total_count": 2,
            "total_size_bytes": 4294967296,
            "total_size": "4.0 GB",
            "note": None,
        },
        "sessions": {
            "source": "X:/Comfy-Cozy/sessions",
            "sessions": [{"session": "portrait", "outcomes": 3}],
            "total_outcomes": 3,
            "note": None,
        },
        "gpu": (
            {
                "available": True,
                "devices": [
                    {
                        "name": "NVIDIA GeForce RTX 4090",
                        "vram_total": "24.0 GB",
                        "vram_free": "20.0 GB",
                        "vram_used": "4.0 GB",
                    }
                ],
                "note": None,
            }
            if gpu_up
            else {
                "available": False,
                "devices": [],
                "note": "ComfyUI is not running — start it to see GPU and VRAM numbers.",
            }
        ),
    }


def _search(found: bool) -> dict:
    if not found:
        return {
            "query": "nope",
            "matches": [],
            "note": (
                "No local models match 'nope'. Try fewer letters — "
                "this searches your disk only, not the internet."
            ),
        }
    return {
        "query": "sdxl",
        "matches": [
            {
                "name": "sdxl_base_1.0.safetensors",
                "model_type": "checkpoints",
                "size": "6.5 GB",
                "family": "sdxl",
                "family_label": "SDXL",
                "status": "ok",
                "glyph": "✓",
                "score": 1.0,
            }
        ],
        "note": None,
    }


# ---------------------------------------------------------------------------
# Help surfaces — every new surface registers and self-describes
# ---------------------------------------------------------------------------


class TestHelp:
    def test_run_help_shows_recipe_flag(self):
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--recipe" in result.output
        assert "--workflow" in result.output

    def test_doctor_help(self):
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower()

    def test_stats_help(self):
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0
        assert "on-device" in result.output.lower()

    def test_model_group_help(self):
        result = runner.invoke(app, ["model", "--help"])
        assert result.exit_code == 0
        assert "search" in result.output

    def test_model_search_help(self):
        result = runner.invoke(app, ["model", "search", "--help"])
        assert result.exit_code == 0
        assert "disk" in result.output.lower()

    def test_models_search_alias_help(self):
        result = runner.invoke(app, ["models", "search", "--help"])
        assert result.exit_code == 0

    def test_all_sixteen_existing_commands_still_registered(self):
        """Additive-only guarantee: the 11 originals + 5 Mile-2 commands keep their names."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for name in (
            "run",
            "inspect",
            "diagnose",
            "parse",
            "sessions",
            "search",
            "orchestrate",
            "autoresearch",
            "autonomous",
            "mcp",
            "models",
            "nodes",
            "find",
            "open",
            "see",
        ):
            assert name in result.output

    def test_models_list_untouched(self):
        """The alias registration must not disturb `cozy models list`."""
        result = runner.invoke(app, ["models", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "search" in result.output


# ---------------------------------------------------------------------------
# cozy run --recipe (INTEND)
# ---------------------------------------------------------------------------


class TestRunRecipe:
    def test_recipe_list_prints_palette(self):
        """`--recipe list` uses the real registry — offline, no mocks needed."""
        result = runner.invoke(app, ["run", "--recipe", "list"])
        assert result.exit_code == 0
        assert "cozy run --recipe" in result.output
        assert "dreamier" in result.output

    def test_applied_recipe_validates_then_executes(self):
        with (
            patch(
                "agent.verbs.intend.apply_recipe_to_session",
                return_value=_applied_recipe_result(),
            ) as apply_mock,
            patch(
                "agent.tools.comfy_execute.handle",
                side_effect=[_VALIDATION_OK, _EXEC_COMPLETE],
            ) as exec_mock,
            patch("agent.tools.comfy_api.handle", return_value=_API_DOWN),
        ):
            result = runner.invoke(app, ["run", "--recipe", "dreamier"])
        assert result.exit_code == 0
        assert "Applied 'dreamier'" in result.output
        assert "cfg: 8.0 -> 6.0" in result.output
        assert "run    complete" in result.output
        apply_mock.assert_called_once_with("dreamier")
        names = [call.args[0] for call in exec_mock.call_args_list]
        assert names == ["validate_before_execute", "execute_with_progress"]
        # Lane C contract: the CLI opts in to the capped success-path log.
        assert exec_mock.call_args_list[1].args[1]["include_progress_log"] is True

    def test_not_applied_exits_1_and_never_executes(self):
        message = "No workflow is loaded yet — load one first, then re-run the recipe."
        with (
            patch(
                "agent.verbs.intend.apply_recipe_to_session",
                return_value=_fall_through_result(message),
            ),
            patch("agent.tools.comfy_execute.handle") as exec_mock,
        ):
            result = runner.invoke(app, ["run", "--recipe", "dreamier"])
        assert result.exit_code == 1
        assert "No workflow is loaded" in result.output
        exec_mock.assert_not_called()

    def test_unknown_recipe_exits_1_with_names(self):
        """Real engine resolution path — a miss never executes anything."""
        with patch("agent.tools.comfy_execute.handle") as exec_mock:
            result = runner.invoke(app, ["run", "--recipe", "zebra-stripes"])
        assert result.exit_code == 1
        assert "zebra-stripes" in result.output
        assert "dreamier" in result.output  # the available names are offered
        assert "Traceback" not in result.output
        exec_mock.assert_not_called()

    def test_workflow_file_loads_into_the_session_before_apply(self, tmp_path, sample_workflow):
        """Defect B2 regression: -w must load through the SESSION seam.

        The old test mocked the load call and asserted the wrong seam
        (workflow_parse.load_workflow — analysis-only, session stays empty),
        locking the bug in. This one uses a real file and asserts the session
        actually holds the workflow at the moment the recipe applies.
        """
        path = tmp_path / "shot_020.json"
        path.write_text(json.dumps(sample_workflow), encoding="utf-8")
        seen: dict = {}

        def apply_spy(text):
            from agent.tools.workflow_patch import get_current_workflow

            seen["at_apply"] = get_current_workflow()
            return _applied_recipe_result()

        with (
            patch("agent.verbs.intend.apply_recipe_to_session", side_effect=apply_spy),
            patch(
                "agent.tools.comfy_execute.handle",
                side_effect=[_VALIDATION_OK, _EXEC_COMPLETE],
            ),
            patch("agent.tools.comfy_api.handle", return_value=_API_DOWN),
        ):
            result = runner.invoke(app, ["run", "--recipe", "dreamier", "--workflow", str(path)])
        assert result.exit_code == 0
        assert seen["at_apply"] is not None, "-w load left the session empty (defect B2)"
        assert seen["at_apply"]["2"]["class_type"] == "KSampler"

    def test_unmocked_load_and_recipe_apply_flow(self, tmp_path, sample_workflow):
        """Full offline flow: real file load -> real recipe apply -> real changes.

        Only the network seam is mocked (validate/execute + the VRAM poll);
        the recipe registry is offline by design. Proves the loaded session
        graph is what the recipe engine mutates — the exact path defect B2
        broke.
        """
        from agent.tools import workflow_patch

        path = tmp_path / "shot_020.json"
        path.write_text(json.dumps(sample_workflow), encoding="utf-8")
        with (
            patch(
                "agent.tools.comfy_execute.handle",
                side_effect=[_VALIDATION_OK, _EXEC_COMPLETE],
            ),
            patch("agent.tools.comfy_api.handle", return_value=_API_DOWN),
        ):
            result = runner.invoke(app, ["run", "--recipe", "dreamier", "-w", str(path)])
        assert result.exit_code == 0
        workflow = workflow_patch.get_current_workflow()
        assert workflow is not None
        assert workflow["2"]["inputs"]["cfg"] == 6.0  # dreamier: cfg -> 6.0
        assert workflow["2"]["inputs"]["sampler_name"] == "dpmpp_2m"
        assert "cfg: 7.0 -> 6.0" in _flat(result.output)  # changes rendered, non-empty

    def test_workflow_file_error_exits_1_before_apply(self, tmp_path):
        missing = tmp_path / "no_such_file.json"
        with patch("agent.verbs.intend.apply_recipe_to_session") as apply_mock:
            result = runner.invoke(
                app, ["run", "--recipe", "dreamier", "--workflow", str(missing)]
            )
        assert result.exit_code == 1
        assert "File not found" in _flat(result.output)
        apply_mock.assert_not_called()

    def test_validation_failure_blocks_execution(self):
        with (
            patch(
                "agent.verbs.intend.apply_recipe_to_session",
                return_value=_applied_recipe_result(),
            ),
            patch("agent.tools.comfy_execute.handle", return_value=_VALIDATION_BAD) as exec_mock,
        ):
            result = runner.invoke(app, ["run", "--recipe", "dreamier"])
        assert result.exit_code == 1
        assert "isn't ready to run" in result.output
        assert "missing required input" in result.output
        assert exec_mock.call_count == 1  # validate only; execute never fired

    def test_comfyui_down_at_validation_exits_1(self):
        with (
            patch(
                "agent.verbs.intend.apply_recipe_to_session",
                return_value=_applied_recipe_result(),
            ),
            patch("agent.tools.comfy_execute.handle", return_value=_API_DOWN) as exec_mock,
        ):
            result = runner.invoke(app, ["run", "--recipe", "dreamier"])
        assert result.exit_code == 1
        assert "ComfyUI is not reachable" in result.output
        assert exec_mock.call_count == 1

    def test_partial_recipe_error_exits_1_and_never_executes(self):
        """Defect B4 regression (Lane D contract): error set = stop, even mid-apply.

        A partial apply reports applied=True AND error set. The CLI must
        print the partial-stop rendering, exit 1, and never validate or
        execute the half-applied workflow.
        """
        partial = _applied_recipe_result()
        partial["error"] = "the scheduler step was rejected"
        partial["steps_run"] = 1
        with (
            patch("agent.verbs.intend.apply_recipe_to_session", return_value=partial),
            patch("agent.tools.comfy_execute.handle") as exec_mock,
        ):
            result = runner.invoke(app, ["run", "--recipe", "dreamier"])
        assert result.exit_code == 1
        flat = _flat(result.output)
        # Lane D partial-stop rendering — never the success header.
        assert "Applied 1 of 4 steps, then stopped: the scheduler step was rejected" in flat
        assert "Applied 'dreamier'" not in flat
        assert "cfg: 8.0 -> 6.0" in flat  # the landed change is still itemized
        exec_mock.assert_not_called()


# ---------------------------------------------------------------------------
# cozy doctor (OWN)
# ---------------------------------------------------------------------------


class TestDoctor:
    def test_healthy_exits_0(self):
        with patch("agent.verbs.own.doctor_report", return_value=_doctor(ok=True)) as m:
            result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Everything looks healthy." in result.output
        m.assert_called_once_with()

    def test_problem_exits_1_with_fix_hint(self):
        with patch("agent.verbs.own.doctor_report", return_value=_doctor(ok=False)):
            result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "No models folder" in result.output
        assert "fix: Check COMFYUI_DATABASE" in result.output
        assert "checks need attention" in result.output


# ---------------------------------------------------------------------------
# cozy stats (OWN)
# ---------------------------------------------------------------------------


class TestStats:
    def test_happy_path(self):
        with patch("agent.verbs.own.stats_report", return_value=_stats(gpu_up=True)) as m:
            result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "checkpoints" in result.output
        assert "portrait: 3 outcome(s)" in result.output
        assert "RTX 4090" in result.output
        m.assert_called_once_with()

    def test_comfyui_down_still_shows_disk_numbers(self):
        with patch("agent.verbs.own.stats_report", return_value=_stats(gpu_up=False)):
            result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "checkpoints" in result.output
        assert "ComfyUI is not running" in result.output


# ---------------------------------------------------------------------------
# cozy model search / cozy models search (OWN)
# ---------------------------------------------------------------------------


class TestModelSearch:
    def test_happy_path_singular(self):
        with patch("agent.verbs.own.search_models", return_value=_search(found=True)) as m:
            result = runner.invoke(app, ["model", "search", "sdxl"])
        assert result.exit_code == 0
        assert "sdxl_base_1.0.safetensors" in result.output
        assert "1 found" in result.output
        m.assert_called_once_with("sdxl")

    def test_plural_alias_same_engine(self):
        with patch("agent.verbs.own.search_models", return_value=_search(found=True)) as m:
            result = runner.invoke(app, ["models", "search", "sdxl"])
        assert result.exit_code == 0
        assert "sdxl_base_1.0.safetensors" in result.output
        m.assert_called_once_with("sdxl")

    def test_no_matches_prints_note(self):
        with patch("agent.verbs.own.search_models", return_value=_search(found=False)):
            result = runner.invoke(app, ["model", "search", "nope"])
        assert result.exit_code == 0
        assert "0 found" in result.output
        assert "internet" in result.output  # the disk-only note surfaced

    def test_query_is_required(self):
        result = runner.invoke(app, ["model", "search"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Glyph output on legacy-encoded stdout (defect B3)
# ---------------------------------------------------------------------------


class TestGlyphEncodingDegradation:
    """Defect B3 regression: glyph output crashed with a raw UnicodeEncodeError
    when stdout was redirected/piped on Windows (cp1252). The fix reconfigures
    the std streams to UTF-8 with replacement at app start — output degrades,
    never dies."""

    @staticmethod
    def _cp1252_stdout(monkeypatch):
        buf = io.BytesIO()
        wrapper = io.TextIOWrapper(buf, encoding="cp1252", newline="")
        monkeypatch.setattr(sys, "stdout", wrapper)
        # Keep stderr hermetic too — the helper touches both streams.
        monkeypatch.setattr(
            sys, "stderr", io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="")
        )
        return buf, wrapper

    def test_cp1252_stream_would_crash_without_the_fix(self, monkeypatch):
        """The live repro: cp1252 cannot encode the check-mark glyph."""
        _buf, wrapper = self._cp1252_stdout(monkeypatch)
        with pytest.raises(UnicodeEncodeError):
            wrapper.write("✓")
            wrapper.flush()

    def test_every_glyph_path_survives_a_cp1252_stdout(self, monkeypatch):
        """Doctor ✓/✗ marks, model health glyphs, and the see sparkline all
        render through a Console on a cp1252 buffer without an exception."""
        from rich.console import Console

        from agent.cli import _ensure_utf8_streams
        from agent.verbs.own import render_doctor_report, render_search_report

        buf, wrapper = self._cp1252_stdout(monkeypatch)
        _ensure_utf8_streams()
        console = Console(file=wrapper, force_terminal=False, width=120)
        console.print(render_doctor_report(_doctor(ok=False)), markup=False, highlight=False)
        console.print(render_search_report(_search(found=True)), markup=False, highlight=False)
        console.print("steps  ⣀⣤⣶⣿⣿⣶⣤⣀  20 of 20", markup=False, highlight=False)
        wrapper.flush()
        data = buf.getvalue()
        assert data  # degraded, not dead
        assert "✓".encode("utf-8") in data  # glyphs now travel as UTF-8 bytes

    def test_helper_leaves_utf8_streams_alone(self, monkeypatch):
        from agent.cli import _ensure_utf8_streams

        wrapper = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="")
        monkeypatch.setattr(sys, "stdout", wrapper)
        monkeypatch.setattr(
            sys, "stderr", io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="")
        )
        _ensure_utf8_streams()
        assert wrapper.encoding == "utf-8"
        assert wrapper.errors == "strict"  # no needless reconfigure

    def test_helper_never_crashes_without_reconfigure_support(self, monkeypatch):
        from agent.cli import _ensure_utf8_streams

        class LegacyStream:
            """A stream with a narrow encoding but no reconfigure() (guarded path)."""

            encoding = "cp1252"

            def write(self, text: str) -> int:
                return len(text)

        monkeypatch.setattr(sys, "stdout", LegacyStream())
        monkeypatch.setattr(sys, "stderr", LegacyStream())
        _ensure_utf8_streams()  # must not raise
