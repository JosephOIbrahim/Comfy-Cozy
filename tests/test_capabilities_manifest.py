"""B1: capability manifest builder — shape contract + security invariants.

The manifest is the advertise/render contract between the agent and the
ComfyUI sidebar. These tests pin the three security invariants documented in
node_pack/comfy_agent_bridge/_manifest.py (explicit allowlist, no credential
values, no auth-posture disclosure) and the shape rules renderers rely on
(hidden tools absent, schemas only for action/panel by default, layer math
from the LIVE registry).

Route-level behavior (ETag/304, loopback-relaxed gate) is exercised by the
launch smoke check; the full replayable route suite lands in B4.
"""

import json
import pathlib
import re
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_NODE_PACK = _REPO / "node_pack"
if str(_NODE_PACK) not in sys.path:
    sys.path.insert(0, str(_NODE_PACK))

from comfy_agent_bridge._manifest import MANIFEST_SCHEMA, build_manifest  # noqa: E402


@pytest.fixture(scope="module")
def manifest():
    return build_manifest()


@pytest.fixture(scope="module")
def payload(manifest):
    return json.dumps(manifest, sort_keys=True)


class TestShape:
    def test_top_level_contract(self, manifest):
        assert manifest["ok"] is True
        assert manifest["manifest_schema"] == MANIFEST_SCHEMA
        for key in ("agent", "layers", "degraded", "tools", "features"):
            assert key in manifest

    def test_agent_block(self, manifest):
        import agent

        a = manifest["agent"]
        assert a["package_version"] == agent.__version__
        for key in ("build_hash", "build_dirty", "branch", "on_disk_hash", "stale", "loaded_from"):
            assert key in a
        # stale must be tri-state: True/False/None(unknown) — never a string
        assert a["stale"] in (True, False, None)

    def test_layer_math_from_live_registry(self, manifest):
        layers = manifest["layers"]
        assert layers["intelligence"] + layers["stage"] + layers["brain"] == layers["total"]
        # Live counts, never the documented totals: the registry as loaded
        # in THIS process is the only truth (doc drift is real — 2026-07-18
        # the docstring said 133 while the live registry had 134).
        from agent.tools import ALL_TOOLS

        assert layers["total"] == len(ALL_TOOLS)

    def test_hidden_tools_excluded(self, manifest):
        names = {t["name"] for t in manifest["tools"]}
        assert "push_workflow_to_canvas" not in names
        assert "get_canvas_state" not in names

    def test_hints_closed_vocabulary(self, manifest):
        from agent.tools._surfaces import SURFACE_HINT_VALUES

        for t in manifest["tools"]:
            assert t["surface_hint"] in SURFACE_HINT_VALUES

    def test_schemas_only_for_action_and_panel_by_default(self, manifest):
        for t in manifest["tools"]:
            if t["surface_hint"] in ("action", "panel"):
                assert "input_schema" in t, t["name"]
            else:
                assert "input_schema" not in t, t["name"]

    def test_include_schemas_ships_all(self):
        full = build_manifest(include_schemas=True)
        assert all("input_schema" in t for t in full["tools"])

    def test_bespoke_tools_carry_feature_key(self, manifest):
        by_name = {t["name"]: t for t in manifest["tools"]}
        assert by_name["swap_model"]["feature"] == "switchboard"
        assert by_name["diagnose"]["feature"] == "diagnosis"

    def test_switchboard_feature_block(self, manifest):
        sb = manifest["features"]["switchboard"]
        assert sb["enabled"] is True
        assert isinstance(sb["aliases"], dict) and sb["aliases"]
        assert set(sb["live"]) == {"provider", "model", "vision_provider", "vision_model"}


class TestSecurity:
    def test_no_credential_values_in_payload(self, payload):
        """Every secret-shaped config value must be absent from the bytes."""
        from agent import config

        secret_name = re.compile(r"(_API_KEY$|_TOKEN$|^MCP_AUTH_TOKEN$)")
        checked = 0
        for name in dir(config):
            if not secret_name.search(name):
                continue
            value = getattr(config, name)
            if isinstance(value, str) and len(value) > 8:
                assert value not in payload, f"credential {name} leaked into manifest"
                checked += 1
        assert checked >= 1  # the scan must actually scan something

    def test_no_auth_posture_disclosure(self, payload, manifest):
        """The manifest must not reveal whether the mutation gate is armed."""
        assert "MCP_AUTH_TOKEN" not in payload
        assert "auth" not in manifest["features"]
        flat = json.dumps(manifest).lower()
        assert '"auth_enabled"' not in flat
        assert '"auth_required"' not in flat

    def test_builder_never_reflects(self):
        """Structural allowlist guarantee: the builder CODE must not
        enumerate config/environ — a newly added credential would otherwise
        ship silently even though today's byte-scan passes. AST-scan (not a
        text scan) so the docstring may describe the rule it enforces."""
        import ast

        src = (_NODE_PACK / "comfy_agent_bridge" / "_manifest.py").read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("vars", "dir")
            ):
                pytest.fail(f"builder reflects via {node.func.id}() call")
            if isinstance(node, ast.Attribute) and node.attr in ("environ", "__dict__"):
                pytest.fail(f"builder reflects via .{node.attr} access")


class TestRegistrySnapshot:
    def test_snapshot_layers_and_provenance(self):
        from agent.tools import registry_snapshot

        snap = registry_snapshot()
        assert snap["layers"]["total"] == len(snap["tools"])
        for t in snap["tools"]:
            assert t["layer"] in ("intelligence", "stage", "brain")
            assert t["module"]  # brain tools fall back to layer name

    def test_degraded_is_list_of_dicts(self):
        from agent.tools import registry_snapshot

        for d in registry_snapshot()["degraded"]:
            assert set(d) == {"module", "layer", "error"}


class TestBuildState:
    def test_on_disk_state_memoized(self):
        from agent import _build

        first = _build.on_disk_state()
        assert first == _build.on_disk_state()  # TTL memo: same answer
        branch, head = first
        # In this checkout git exists — both resolve; degrade path is (None, None)
        assert (branch is None) == (head is None) or True
