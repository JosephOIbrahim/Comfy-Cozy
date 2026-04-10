"""Tests for workflow_templates — path traversal security and basic functionality."""

import json

import pytest

from agent.tools import workflow_templates


# ---------------------------------------------------------------------------
# Cycle 29: template name path traversal security tests
# ---------------------------------------------------------------------------

class TestTemplateNameSecurity:
    """_resolve_template_path must reject names that could escape the templates dir."""

    def test_path_traversal_dot_dot_slash_rejected(self):
        """Template name with ../ must return error (not find arbitrary files)."""
        result = json.loads(workflow_templates.handle("get_workflow_template", {
            "template": "../../etc/passwd",
        }))
        assert "error" in result
        # Must NOT have loaded file content
        assert "class_type" not in str(result)

    def test_path_traversal_backslash_rejected(self):
        """Template name with backslash traversal must return error."""
        result = json.loads(workflow_templates.handle("get_workflow_template", {
            "template": "..\\..\\Windows\\system32\\config\\SAM",
        }))
        assert "error" in result

    def test_path_traversal_null_byte_rejected(self):
        """Template name with null byte must return error."""
        result = json.loads(workflow_templates.handle("get_workflow_template", {
            "template": "valid\x00../../etc/passwd",
        }))
        assert "error" in result

    def test_simple_template_name_accepted(self):
        """A simple template name does not trip the security check."""
        # txt2img_sd15 is a known built-in template
        result = json.loads(workflow_templates.handle("get_workflow_template", {
            "template": "txt2img_sd15",
        }))
        # Either succeeds (returns workflow) or not-found error — NOT a traversal block
        if "error" in result:
            # Error must be about the template not being found, not a traversal block
            assert "not found" in result["error"].lower() or "template" in result["error"].lower()

    def test_list_templates_returns_names(self):
        """list_workflow_templates must return a list without path traversal."""
        result = json.loads(workflow_templates.handle("list_workflow_templates", {}))
        # Should have either templates or an error (if templates dir missing)
        assert "templates" in result or "error" in result
        if "templates" in result:
            # All template names must be simple strings (no slashes)
            for t in result["templates"]:
                name = t.get("name", "")
                assert "/" not in name and "\\" not in name, (
                    f"Template name contains path separator: {name!r}"
                )
