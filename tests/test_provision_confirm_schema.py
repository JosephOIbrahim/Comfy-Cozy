"""Schema contract crucible for the confirm-MCP brick.

The keystone gate (agent/tools/__init__.py) BLOCKS PROVISION-class tools unless
tool_input["confirm"] parses truthy. A schema-validating MCP client strips any
field absent from the advertised input_schema, so `confirm` must be declared in
each gated tool's schema or the op is permanently bricked over MCP. This test
exercises the schema layer the existing handle()-direct crucible bypasses.

PATH-D FREEZE: the stage tool `provision_download` (agent/stage/provision_tools.py)
has the identical gap but is frozen — intentionally NOT covered here. See the RFC note.
"""

import pytest

from agent.tools import comfy_provision, provision_pipeline


def _schema_for(module, tool_name):
    for tool in module.TOOLS:
        if tool["name"] == tool_name:
            return tool["input_schema"]
    raise AssertionError(f"{tool_name} not found in {module.__name__}.TOOLS")


# (module, tool_name) for every editable PROVISION-gated tool that flows through
# the keystone / its own confirm gate. provision_download is FROZEN -> excluded.
_GATED_TOOLS = [
    (comfy_provision, "download_model"),
    (comfy_provision, "install_node_pack"),
    (comfy_provision, "repair_workflow"),
    (provision_pipeline, "provision_model"),
]


class TestProvisionConfirmSchema:
    @pytest.mark.parametrize("module,tool_name", _GATED_TOOLS)
    def test_confirm_declared_as_boolean(self, module, tool_name):
        schema = _schema_for(module, tool_name)
        props = schema.get("properties", {})
        assert "confirm" in props, (
            f"{tool_name} input_schema must declare 'confirm' or the MCP client "
            f"strips it and the gate blocks the op forever"
        )
        assert props["confirm"].get("type") == "boolean", (
            f"{tool_name} 'confirm' must be a boolean, got {props['confirm']!r}"
        )

    @pytest.mark.parametrize("module,tool_name", _GATED_TOOLS)
    def test_confirm_not_required(self, module, tool_name):
        # confirm must default-false / opt-in: forcing it into `required` would
        # train a model to always emit it and could weaken intent-gating.
        schema = _schema_for(module, tool_name)
        assert "confirm" not in schema.get("required", []), (
            f"{tool_name} must NOT list 'confirm' as required"
        )
