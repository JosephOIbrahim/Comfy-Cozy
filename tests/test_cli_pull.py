"""CLI wiring tests for the Mile-6 verb: pull (OPEN-IN).

The engine layer (agent/verbs/pull_canvas.py) carries its own test file
(tests/test_verbs_pull.py); these tests pin the CLI layer only — command
registration, help text, happy-path rendering with the engine mocked,
degraded-path exit codes, and the --file flag routing. All mocked: no
ComfyUI server, no network, no API key.
"""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import agent.config as config
from agent.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_sessions_dir(tmp_path, monkeypatch):
    """``cozy pull`` now restores/persists the CLI session sidecar (defect
    B1) — keep every test's sidecar reads and writes out of the real
    sessions directory."""
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path / "sessions")


def _flat(output: str) -> str:
    """Collapse console line-wrapping so phrase assertions survive any width."""
    return " ".join(output.split())


# ---------------------------------------------------------------------------
# Fixture-shaped results (match the pull_canvas engine contract's dict shape)
# ---------------------------------------------------------------------------


def _pull_result(**overrides: object) -> dict:
    """A pull_canvas result dict with contract-complete keys."""
    result: dict = {
        "ok": True,
        "pulled": True,
        "applied": True,
        "initial_load": False,
        "refused": False,
        "source": "canvas",
        "node_count": 5,
        "changes": 3,
        "summary": {
            "nodes_added": [{"id": "9", "class_type": "LoraLoader"}],
            "nodes_removed": [],
            "params_changed": [{"node": "3", "param": "steps", "old": 20, "new": 30}],
            "links_rewired": 1,
        },
        "message": "Pulled your canvas edits into the session — one undo away.",
    }
    result.update(overrides)
    return result


# ---------------------------------------------------------------------------
# Help / registration
# ---------------------------------------------------------------------------


class TestPullHelp:
    def test_pull_registered_with_help(self):
        result = runner.invoke(app, ["pull", "--help"])
        assert result.exit_code == 0
        assert "canvas edits back into the session" in _flat(result.output)

    def test_pull_help_mentions_file_flag(self):
        result = runner.invoke(app, ["pull", "--help"])
        assert result.exit_code == 0
        assert "--file" in result.output

    def test_pull_listed_in_top_level_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "pull" in result.output


# ---------------------------------------------------------------------------
# Happy path (engine mocked)
# ---------------------------------------------------------------------------


class TestPullHappyPath:
    def test_pull_defaults_to_canvas_source(self):
        ok = _pull_result()
        with patch("agent.verbs.pull_canvas.pull_canvas", return_value=ok) as m:
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        m.assert_called_once_with(source="canvas", file=None)

    def test_pull_prints_rendered_summary(self):
        ok = _pull_result()
        with patch("agent.verbs.pull_canvas.pull_canvas", return_value=ok):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        flat = _flat(result.output)
        assert "one undo away" in flat
        assert "+ LoraLoader joined as node 9" in flat
        assert "~ steps on node 3: 20 -> 30" in flat
        assert "~ 1 connection rewired" in flat

    def test_pull_file_flag_routes_to_file_source(self):
        ok = _pull_result(source="file")
        with patch("agent.verbs.pull_canvas.pull_canvas", return_value=ok) as m:
            result = runner.invoke(app, ["pull", "--file", "shot_020.json"])
        assert result.exit_code == 0
        m.assert_called_once_with(source="file", file="shot_020.json")

    def test_pull_empty_diff_exits_zero(self):
        # "Already match" is a success per the contract: ok=True, applied=False.
        match = _pull_result(
            applied=False,
            changes=0,
            summary=None,
            message="Canvas and session already match — nothing to pull.",
        )
        with patch("agent.verbs.pull_canvas.pull_canvas", return_value=match):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        assert "already match" in _flat(result.output)

    def test_pull_initial_load_exits_zero(self):
        initial = _pull_result(
            applied=False,
            initial_load=True,
            changes=0,
            summary=None,
            message="Loaded your canvas graph as the session baseline (5 nodes).",
        )
        with patch("agent.verbs.pull_canvas.pull_canvas", return_value=initial):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        assert "session baseline" in _flat(result.output)


# ---------------------------------------------------------------------------
# Degraded paths (engine mocked; exit code 1, human-worded message)
# ---------------------------------------------------------------------------


class TestPullDegraded:
    def test_pull_comfyui_down_exits_one(self):
        down = _pull_result(
            ok=False,
            pulled=False,
            applied=False,
            node_count=0,
            changes=0,
            summary=None,
            message=(
                "ComfyUI isn't reachable, so there's no canvas to pull from. "
                "Your session workflow is untouched."
            ),
        )
        with patch("agent.verbs.pull_canvas.pull_canvas", return_value=down):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 1
        assert "isn't reachable" in _flat(result.output)
        assert "session workflow is untouched" in _flat(result.output)

    def test_pull_refused_broken_dag_exits_one(self):
        refused = _pull_result(
            ok=False,
            applied=False,
            refused=True,
            changes=0,
            summary=None,
            message=(
                "Can't pull this graph: KSampler (node 5) input 'positive' points "
                "at node 3, which is not in the graph. Your session workflow is "
                "untouched."
            ),
        )
        with patch("agent.verbs.pull_canvas.pull_canvas", return_value=refused):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 1
        assert "points at node 3" in _flat(result.output)
        assert "untouched" in _flat(result.output)

    def test_pull_degraded_prints_no_summary_lines(self):
        down = _pull_result(
            ok=False,
            pulled=False,
            applied=False,
            node_count=0,
            changes=0,
            summary=None,
            message="The canvas buffer is empty — nothing to pull yet.",
        )
        with patch("agent.verbs.pull_canvas.pull_canvas", return_value=down):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 1
        assert "joined as node" not in _flat(result.output)
        assert "rewired" not in _flat(result.output)
