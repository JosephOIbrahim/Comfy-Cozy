"""Seam test required by the science harness; real producer -> real consumer,
edge-mocked only; flips A-SEAM.

Drives the REAL ``comfy_discover._handle_find_missing_nodes`` (producer) through
the REAL ``comfy_provision._handle_repair_workflow`` (consumer). repair_workflow
calls the discover handle internally — that call is NOT stubbed. Mocks sit only
at the true IO edges of the producer:

- ComfyUI ``/object_info`` HTTP fetch (``httpx.Client``)
- ComfyUI-Manager registry files (``_MANAGER_DIR`` -> tmp extension-node-map.json)
- installed-pack filesystem check (``CUSTOM_NODES_DIR`` -> empty tmp dir)
- deprecation registry fetch (``node_replacement._fetch_replacements``)

and at the consumer's install edge (``_handle_install_node_pack`` spy — tests
must never install). Guards ledger C-P0-1: the producer emits
``missing_nodes``/``node_type``/``pack_title``/``pack_url``; the consumer used to
read ``missing``/``class_type``/``pack_name`` and silently reported "clean".
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.tools import comfy_discover, comfy_provision, workflow_patch

# One missing node resolvable to a pack (title + url), one unresolvable.
_EXTENSION_MAP = {
    "https://github.com/cubiq/ComfyUI_IPAdapter_plus": [
        ["IPAdapterUnifiedLoader", "IPAdapterApply"],
        {"title_aux": "ComfyUI_IPAdapter_plus"},
    ],
}

_WORKFLOW = {
    "1": {"class_type": "KSampler", "inputs": {}},                 # installed
    "2": {"class_type": "IPAdapterUnifiedLoader", "inputs": {}},   # missing, resolvable
    "3": {"class_type": "TotallyUnknownNode_X", "inputs": {}},     # missing, unresolvable
}

_OBJECT_INFO = {"KSampler": {}}  # live ComfyUI knows only KSampler


@pytest.fixture(autouse=True)
def _reset_discover_cache():
    """Clear registry cache so the tmp extension map is actually read."""
    comfy_discover._clear_cache()
    yield
    comfy_discover._clear_cache()


@pytest.fixture
def seam_edges(tmp_path):
    """Patch ONLY the producer's true IO edges; everything between stays real."""
    manager_dir = tmp_path / "ComfyUI-Manager"
    manager_dir.mkdir()
    (manager_dir / "extension-node-map.json").write_text(
        json.dumps(_EXTENSION_MAP), encoding="utf-8",
    )
    cn_dir = tmp_path / "Custom_Nodes"
    cn_dir.mkdir()  # empty -> pack not installed

    workflow_patch._get_state()["current_workflow"] = dict(_WORKFLOW)

    mock_resp = MagicMock()
    mock_resp.json.return_value = _OBJECT_INFO
    mock_resp.raise_for_status = MagicMock()

    install_spy = MagicMock(
        return_value=json.dumps({"installed": True, "message": "spy"}))

    with patch.object(comfy_discover, "_MANAGER_DIR", manager_dir), \
         patch.object(comfy_discover, "CUSTOM_NODES_DIR", cn_dir), \
         patch("agent.tools.node_replacement._fetch_replacements", return_value={}), \
         patch("agent.tools.comfy_discover.httpx.Client") as mock_cls, \
         patch("agent.tools.comfy_provision._handle_install_node_pack", install_spy):
        mock_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        yield install_spy

    workflow_patch._get_state()["current_workflow"] = None


class TestRepairDiscoverSeam:
    def test_producer_emits_contract_shape(self, seam_edges):
        """Sanity: the real producer reports both missing nodes with node_type keys."""
        result = json.loads(comfy_discover.handle("find_missing_nodes", {}))
        assert result["status"] == "missing_nodes"
        assert result["missing_count"] == 2
        by_type = {m["node_type"]: m for m in result["missing_nodes"]}
        assert by_type["IPAdapterUnifiedLoader"]["pack_title"] == "ComfyUI_IPAdapter_plus"
        assert by_type["TotallyUnknownNode_X"]["pack_title"] is None

    def test_case_a_report_path_sees_real_missing_nodes(self, seam_edges):
        """auto_install=False -> 'report' with counts/packs/unresolved from the producer."""
        result = json.loads(
            comfy_provision._handle_repair_workflow({"auto_install": False}))

        assert result["status"] == "report", result
        assert result["missing_count"] == 2
        assert result["packs_found"] == 1
        assert result["unresolved_nodes"] == ["TotallyUnknownNode_X"]
        assert result["packs_installed"] == 0
        assert seam_edges.call_count == 0, "report path must not install"

    def test_case_b_default_auto_install_gates_without_installing(self, seam_edges):
        """Default auto_install (no confirm) -> 'needs_confirmation'; nothing installed."""
        result = json.loads(comfy_provision._handle_repair_workflow({}))

        assert result["status"] == "needs_confirmation", result
        assert result["missing_count"] == 2
        packs = result["packs_to_install"]
        assert len(packs) == 1
        # pack_title/pack_url from the producer must propagate into the pack listing
        assert packs[0]["name"] == "ComfyUI_IPAdapter_plus"
        assert packs[0]["url"] == "https://github.com/cubiq/ComfyUI_IPAdapter_plus"
        assert packs[0]["nodes"] == ["IPAdapterUnifiedLoader"]
        assert result["unresolved_nodes"] == ["TotallyUnknownNode_X"]
        assert seam_edges.call_count == 0, "gated path must install NOTHING"
