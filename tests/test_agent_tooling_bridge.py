"""Tests for Track 2-4 agent tooling: canvas bridge, parser, assets, vision
cache, profiling, output watcher, proactive memory.

All mocked / pure-logic — no live ComfyUI required. Network-touching handlers
are exercised via their internal logic seams or with httpx patched.
"""

import json
import os
import tempfile
from unittest.mock import patch

import agent.tools as T
from agent.tools import (
    canvas_bridge,
    exec_profile,
    local_assets,
    proactive_memory,
    ui_api_parser,
    vision_cache,
)


def _call(name, **kw):
    return json.loads(T.handle(name, kw))


# --------------------------------------------------------------------------- #
# #2 — UI -> API parser (P3.1)
# --------------------------------------------------------------------------- #
OBJ_INFO = {
    "KSampler": {
        "input": {
            "required": {
                "model": ["MODEL"],
                "seed": ["INT", {"default": 0}],
                "steps": ["INT", {"default": 20}],
                "cfg": ["FLOAT", {"default": 8.0}],
                "sampler_name": [["euler", "dpmpp_2m"]],
                "scheduler": [["normal", "karras"]],
                "positive": ["CONDITIONING"],
                "negative": ["CONDITIONING"],
                "latent_image": ["LATENT"],
                "denoise": ["FLOAT", {"default": 1.0}],
            }
        }
    }
}

UI_WF = {
    "nodes": [
        {
            "id": 1,
            "type": "KSampler",
            "widgets_values": [123, "randomize", 20, 8.0, "euler", "normal", 1.0],
            "inputs": [{"name": "model", "link": 10}, {"name": "positive", "link": 11}],
        },
        {"id": 2, "type": "CustomXYZ", "widgets_values": [1]},
    ],
    "links": [[10, 5, 0, 1, 0, "MODEL"], [11, 6, 0, 1, 1, "CONDITIONING"]],
}


class TestUIAPIParser:
    def test_seed_maps_from_schema_order(self):
        api, _ = ui_api_parser._ui_to_api(UI_WF, OBJ_INFO)
        assert api["1"]["inputs"]["seed"] == 123

    def test_control_after_generate_consumed_not_mapped(self):
        api, _ = ui_api_parser._ui_to_api(UI_WF, OBJ_INFO)
        # 'randomize' is the control value — must NOT shift steps off
        assert api["1"]["inputs"]["steps"] == 20
        assert api["1"]["inputs"]["cfg"] == 8.0

    def test_combo_widget_maps(self):
        api, _ = ui_api_parser._ui_to_api(UI_WF, OBJ_INFO)
        assert api["1"]["inputs"]["sampler_name"] == "euler"

    def test_connections_mapped(self):
        api, _ = ui_api_parser._ui_to_api(UI_WF, OBJ_INFO)
        assert api["1"]["inputs"]["model"] == ["5", 0]
        assert api["1"]["inputs"]["positive"] == ["6", 0]

    def test_unmappable_node_surfaced_not_guessed(self):
        api, unmapped = ui_api_parser._ui_to_api(UI_WF, OBJ_INFO)
        assert "2" not in api
        assert any(u["class_type"] == "CustomXYZ" for u in unmapped)

    def test_non_ui_workflow_errors(self):
        result = _call("parse_ui_workflow", workflow={"1": {"class_type": "X"}})
        assert "error" in result

    def test_missing_args_errors(self):
        result = _call("parse_ui_workflow")
        assert "error" in result


# --------------------------------------------------------------------------- #
# #9 — Vision cache (P4.2)
# --------------------------------------------------------------------------- #
class TestVisionCache:
    def setup_method(self):
        vision_cache._cache.clear()

    def test_identical_hash_hits(self):
        vision_cache._store(0, "ANALYSIS_A")
        assert vision_cache._lookup(0) == "ANALYSIS_A"

    def test_near_identical_within_threshold_hits(self):
        vision_cache._store(0, "ANALYSIS_A")
        assert vision_cache._lookup(0b1) == "ANALYSIS_A"  # 1-bit diff <= 2

    def test_boundary_distance_does_not_false_dedup(self):
        vision_cache._store(0, "ANALYSIS_A")
        assert vision_cache._lookup(0b11111) is None  # 5-bit diff > 2

    def test_empty_path_errors(self):
        assert "error" in _call("analyze_image_cached", image_path="")

    def test_cache_evicts_over_max(self):
        for i in range(vision_cache._CACHE_MAX + 10):
            vision_cache._store(1 << (i % 60), f"a{i}")
        assert len(vision_cache._cache) <= vision_cache._CACHE_MAX


# --------------------------------------------------------------------------- #
# #5 — Execution profiling (P2.3)
# --------------------------------------------------------------------------- #
PROFILE = {
    "nodes": [
        {"node_id": "a", "class_type": "KSampler", "start": 2, "duration_ms": 1000},
        {"node_id": "b", "class_type": "VAEDecode", "start": 1, "duration_ms": 50},
        {"node_id": "c", "class_type": "LoadImage", "start": 3, "duration_ms": 0},
    ]
}


class TestExecProfile:
    def test_ordered_by_start(self):
        r = json.loads(exec_profile._profile_from_payload(PROFILE))
        assert r["nodes"][0]["node_id"] == "b"

    def test_cached_node_marked(self):
        r = json.loads(exec_profile._profile_from_payload(PROFILE))
        cached = {n["node_id"]: n["cached"] for n in r["nodes"]}
        assert cached["c"] is True

    def test_vram_reported_unavailable(self):
        r = json.loads(exec_profile._profile_from_payload(PROFILE))
        assert "unavailable" in r["vram"]

    def test_regression_flagged_and_cached_excluded(self):
        exec_profile._baselines.clear()
        json.loads(exec_profile._profile_from_payload(
            PROFILE, baseline_key="k", save_baseline=True))
        slow = json.loads(json.dumps(PROFILE))
        for n in slow["nodes"]:
            if n["node_id"] == "a":
                n["duration_ms"] = 2000
        r = json.loads(exec_profile._profile_from_payload(slow, baseline_key="k"))
        assert r["regression_flagged"] is True
        assert all(x["node_id"] != "c" for x in r["regressions"])

    def test_missing_prompt_id_errors(self):
        assert "error" in _call("get_execution_profile")


# --------------------------------------------------------------------------- #
# #8 — Output watcher (P2.4)
# --------------------------------------------------------------------------- #
class TestOutputWatcher:
    def test_diff_returns_exactly_new_files(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "old.png"), "w").close()
        begin = _call("watch_outputs_begin", label="t1", extra_roots=[d])
        assert begin["watching"] is True
        open(os.path.join(d, "new1.png"), "w").close()
        open(os.path.join(d, "new2.png"), "w").close()
        diff = _call("watch_outputs_diff", label="t1")
        names = sorted(os.path.basename(p) for p in diff["new_files"])
        assert names == ["new1.png", "new2.png"]

    def test_catches_writes_outside_output_when_root_watched(self):
        d = tempfile.mkdtemp()
        _call("watch_outputs_begin", label="t2", extra_roots=[d])
        open(os.path.join(d, "custom_save.png"), "w").close()
        diff = _call("watch_outputs_diff", label="t2")
        assert any("custom_save.png" in p for p in diff["new_files"])

    def test_unrelated_preexisting_not_flagged(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "pre.png"), "w").close()
        _call("watch_outputs_begin", label="t3", extra_roots=[d])
        diff = _call("watch_outputs_diff", label="t3")
        assert diff["new_files"] == []

    def test_unknown_label_errors(self):
        assert "error" in _call("watch_outputs_diff", label="nope")

    def test_missing_label_errors(self):
        assert "error" in _call("watch_outputs_begin")


# --------------------------------------------------------------------------- #
# #10 — Proactive memory (P4.3)
# --------------------------------------------------------------------------- #
class TestProactiveMemory:
    def test_overlap_scores_relevant(self):
        cur = {"KSampler", "CLIPTextEncode"}
        assert proactive_memory._score({"class_types": ["KSampler"]}, cur, 0, 3) >= 1.0

    def test_no_overlap_below_threshold(self):
        cur = {"KSampler"}
        assert proactive_memory._score({"class_types": ["Foo"]}, cur, 0, 3) < 1.0

    def test_extract_class_types_from_workflow(self):
        cts = proactive_memory._extract_class_types(
            {"workflow": {"1": {"class_type": "KSampler"}}})
        assert "KSampler" in cts

    def test_no_class_types_surfaces_nothing(self):
        assert _call("surface_relevant_memory", class_types=[])["surfaced"] == []

    def test_irrelevant_memory_not_injected(self):
        # get_learned_patterns returns only unrelated patterns; a Seedance
        # request must surface nothing (no noise).
        unrelated = json.dumps({"patterns": [{"class_types": ["TotallyUnrelated"]}]})

        def fake_dispatch(name, tool_input):
            if name == "get_learned_patterns":
                return unrelated
            return json.dumps({"error": "unexpected"})

        with patch("agent.tools.handle", side_effect=fake_dispatch):
            r = json.loads(proactive_memory._handle_surface_relevant_memory(
                {"class_types": ["SeedanceSampler"]}))
        assert r["surfaced"] == []

    def test_relevant_memory_is_surfaced(self):
        related = json.dumps({"patterns": [
            {"class_types": ["KSampler"], "note": "use 25 steps"},
            {"class_types": ["TotallyUnrelated"]},
        ]})

        def fake_dispatch(name, tool_input):
            if name == "get_learned_patterns":
                return related
            return json.dumps({"error": "unexpected"})

        with patch("agent.tools.handle", side_effect=fake_dispatch):
            r = json.loads(proactive_memory._handle_surface_relevant_memory(
                {"class_types": ["KSampler"]}))
        assert len(r["surfaced"]) == 1
        assert r["surfaced"][0]["class_types"] == ["KSampler"]


# --------------------------------------------------------------------------- #
# #7 — Local assets (P3.2)
# --------------------------------------------------------------------------- #
class TestLocalAssets:
    def test_hamming(self):
        assert local_assets._hamming(255, 255) == 0
        assert local_assets._hamming(0, 1) == 1

    def test_list_returns_assets_key(self):
        r = _call("list_assets", source="both")
        assert "assets" in r

    def test_invalid_source_coerced(self):
        r = _call("list_assets", source="nonsense")
        assert "assets" in r

    def test_search_filter_and_cap(self):
        d = tempfile.mkdtemp()
        for i in range(5):
            open(os.path.join(d, f"img_{i}.png"), "w").close()
        open(os.path.join(d, "other.png"), "w").close()
        # local_assets scans config roots, not arbitrary dirs; exercise _scan
        from pathlib import Path
        items = local_assets._scan([Path(d)], "img_")
        assert len(items) == 5
        assert all("img_" in it["name"] for it in items)

    def test_collapse_dupes_helper(self):
        # Two identical tiny images collapse to one.
        from PIL import Image
        d = tempfile.mkdtemp()
        p1 = os.path.join(d, "a.png")
        p2 = os.path.join(d, "b.png")
        Image.new("RGB", (16, 16), (100, 100, 100)).save(p1)
        Image.new("RGB", (16, 16), (100, 100, 100)).save(p2)
        items = [{"path": p1, "name": "a.png"}, {"path": p2, "name": "b.png"}]
        kept, removed = local_assets._collapse(items)
        assert removed == 1
        assert len(kept) == 1


# --------------------------------------------------------------------------- #
# Phase 0 / 1B — Canvas bridge (push + read-back) with httpx mocked
# --------------------------------------------------------------------------- #
class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class TestCanvasBridge:
    # These call the handler directly (canvas_bridge.handle) rather than via
    # T.handle: the pre-dispatch gate is exhaustively covered by test_gate.py,
    # and these assert the module's own request/response logic in isolation.
    def _h(self, name, **kw):
        return json.loads(canvas_bridge.handle(name, kw))

    def test_push_requires_workflow_or_path(self):
        assert "error" in self._h("push_workflow_to_canvas")

    def test_push_rejects_non_dict_workflow(self):
        assert "error" in self._h("push_workflow_to_canvas", workflow="not a dict")

    def test_push_success(self):
        with patch("agent.tools.canvas_bridge.httpx.post",
                   return_value=_Resp(200, {"ok": True})):
            r = self._h("push_workflow_to_canvas", workflow={"1": {"class_type": "X"}},
                        reason="test")
        assert r["pushed"] is True

    def test_push_404_explains_missing_pack(self):
        with patch("agent.tools.canvas_bridge.httpx.post",
                   return_value=_Resp(404, text="not found")):
            r = self._h("push_workflow_to_canvas", workflow={"1": {"class_type": "X"}})
        assert "error" in r and "node pack" in r["error"]

    def test_push_connect_error_clean(self):
        import httpx
        with patch("agent.tools.canvas_bridge.httpx.post",
                   side_effect=httpx.ConnectError("refused")):
            r = self._h("push_workflow_to_canvas", workflow={"1": {"class_type": "X"}})
        assert "error" in r and "not reachable" in r["error"]

    def test_get_canvas_state_no_edit_yet(self):
        with patch("agent.tools.canvas_bridge.httpx.get",
                   return_value=_Resp(200, {"workflow": None, "note": "No artist edit captured yet."})):
            r = self._h("get_canvas_state")
        assert r["workflow"] is None

    def test_get_canvas_state_returns_edit(self):
        edit = {"1": {"class_type": "KSampler", "inputs": {"seed": 7}}}
        with patch("agent.tools.canvas_bridge.httpx.get",
                   return_value=_Resp(200, {"workflow": edit})):
            r = self._h("get_canvas_state")
        assert r["workflow"] == edit
