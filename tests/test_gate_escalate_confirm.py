"""KEYSTONE crucible — ESCALATE (PROVISION) now BLOCKS without explicit confirm.

Closes the prompt->autonomous-fetch / prompt->RCE hole from the provision recon:
code-executing PROVISION ops (download_model, install_node_pack, provision_*) were
ESCALATE = logged-but-allowed-through. Now ESCALATE requires `confirm: true`, else it
is BLOCKED (no dispatch).

Adversarial closure-proof:
  - a simulated prompt CANNOT trigger install/download without confirmation (BLOCKED),
  - a confirmed call still PROCEEDS to the handler,
  - the PR #20 fluid path (loaded-workflow REVERSIBLE writes) does NOT regress,
  - destructive uninstall stays hard-LOCKED.

No network / no subprocess: the "confirmed -> dispatched" positives use a private-IP
URL (SSRF-rejected pre-fetch) and a non-HTTPS URL (rejected pre-clone), so the handler
runs but performs no real fetch/install.
"""

import copy
from collections import deque

import pytest

from agent.tools import handle, workflow_patch

_BLOCK = "auto-blocked"  # distinctive substring of the ESCALATE needs-confirm block


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr("agent.config.GATE_ENABLED", True, raising=False)


class TestEscalateBlocksWithoutConfirm:
    # --- NEGATIVE: a prompt WITHOUT confirm is BLOCKED (handler never dispatched) ---
    def test_install_node_pack_blocked_without_confirm(self):
        r = handle("install_node_pack", {"url": "https://github.com/foo/bar", "name": "bar"})
        assert _BLOCK in r, r
        assert "confirmation" in r.lower(), r

    def test_download_model_blocked_without_confirm(self):
        r = handle("download_model", {
            "url": "https://10.0.0.1/m.safetensors",
            "model_type": "checkpoints", "filename": "m.safetensors",
        })
        assert _BLOCK in r, r
        assert "confirmation" in r.lower(), r

    # --- POSITIVE: a CONFIRMED call PROCEEDS to the handler (no real fetch/install) ---
    def test_download_model_confirmed_dispatches(self):
        # private-IP URL => handler's SSRF check rejects BEFORE any network call
        r = handle("download_model", {
            "url": "https://10.0.0.1/m.safetensors",
            "model_type": "checkpoints", "filename": "m.safetensors",
            "confirm": True,
        })
        assert _BLOCK not in r, r                       # gate did NOT block -> dispatched
        assert ("denied" in r.lower()) or ("not allowed" in r.lower()), r  # handler SSRF ran

    def test_install_node_pack_confirmed_dispatches(self):
        # non-HTTPS URL => handler's URL validation rejects BEFORE git clone
        r = handle("install_node_pack", {
            "url": "http://github.com/foo/bar", "name": "bar", "confirm": True,
        })
        assert _BLOCK not in r, r                       # gate did NOT block -> dispatched
        # (handler ran its own HTTPS/host validation; no clone performed)

    # --- NO-REGRESSION: PR #20 fluid path (loaded-workflow REVERSIBLE write) still passes ---
    def test_loaded_workflow_write_not_regressed(self, sample_workflow):
        st = workflow_patch._get_state()
        st["base_workflow"] = copy.deepcopy(sample_workflow)
        st["current_workflow"] = copy.deepcopy(sample_workflow)
        st["history"] = deque(maxlen=workflow_patch._MAX_HISTORY)
        st["_engine"] = None
        r = handle("set_input", {"node_id": "3", "input_name": "text", "value": "still fluid"})
        assert _BLOCK not in r, r          # set_input is REVERSIBLE, not ESCALATE
        assert "Gate denied" not in r, r   # #20 fail-open still holds
        assert st["current_workflow"]["3"]["inputs"]["text"] == "still fluid"

    # --- destructive op stays hard-LOCKED (keystone touches only the ESCALATE branch) ---
    def test_uninstall_still_locked(self):
        r = handle("uninstall_node_pack", {"name": "somepack"})
        assert ("destructive" in r.lower()) or ("cannot be auto-executed" in r.lower()), r
        assert _BLOCK not in r, r          # LOCKED message, distinct from the ESCALATE block


class TestEscalateConfirmLenientParse:
    """The keystone must admit the string forms an over-the-wire JSON client sends
    (confirm='true') AND keep blocking when confirm is absent / False / 'false'.
    Mirrors the repair_workflow handler parse (comfy_provision.py:985-986)."""

    _PRIVATE_DL = {
        "url": "https://10.0.0.1/m.safetensors",
        "model_type": "checkpoints",
        "filename": "m.safetensors",
    }

    @pytest.mark.parametrize("confirm_value", [True, "true", "True", "1", "yes"])
    def test_truthy_confirm_passes_gate(self, confirm_value):
        # gate must NOT block; handler then SSRF-rejects the private IP (no network)
        r = handle("download_model", {**self._PRIVATE_DL, "confirm": confirm_value})
        assert _BLOCK not in r, r
        assert ("denied" in r.lower()) or ("not allowed" in r.lower()), r

    @pytest.mark.parametrize("confirm_value", [False, "false", "False", "0", "no", ""])
    def test_falsy_confirm_still_blocks(self, confirm_value):
        r = handle("download_model", {**self._PRIVATE_DL, "confirm": confirm_value})
        assert _BLOCK in r, r
        assert "confirmation" in r.lower(), r

    def test_absent_confirm_still_blocks(self):
        r = handle("download_model", dict(self._PRIVATE_DL))
        assert _BLOCK in r, r
        assert "confirmation" in r.lower(), r
