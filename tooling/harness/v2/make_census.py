#!/usr/bin/env python
"""Strict partition census of the live tool registry (v2 plan section 4.4).

Every registered name lands in EXACTLY ONE bucket; the partition is validated
against the live registry at build time, so the arithmetic cannot drift from
the prose. Output: tooling/harness/v2/census.json (binding) + CENSUS.md (human).

Buckets:
  keep          name survives unchanged in the 6.0 core surface
  merge_away    name removed from the list; dispatch-level alias -> survivor
  delete        name removed; tombstone error names the replacement
  provisioning  the 11-name family collapsing to 5 (4 kept + 1 new)
  scene_pack    USD-gated optional pack (registered only when HAS_USD)
  nim_pack      podman-gated optional pack (v2 plan 4.11 — parked, not deleted)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

KEEP = [
    "add_node", "add_note", "analyze_image", "apply_optimization", "apply_recipe",
    "apply_workflow_patch", "check_model_compatibility", "check_node_updates",
    "check_tensorrt_status", "check_workflow_deprecations", "classify_workflow",
    "compare_outputs", "connect_nodes", "delete_node", "discover", "execute_workflow",
    "find_missing_nodes", "get_all_nodes", "get_canvas_state", "get_editable_fields",
    "get_execution_status", "get_experience_stats", "get_history",
    "get_install_instructions", "get_learned_patterns", "get_node_info",
    "get_node_replacements", "get_queue_status", "get_recommendations",
    "get_system_stats", "get_workflow_diff", "get_workflow_template",
    "identify_model_family", "iterative_refine", "list_custom_nodes", "list_models",
    "list_recipes", "list_sessions", "list_workflow_templates", "load_session",
    "load_workflow", "migrate_deprecated_nodes", "predict_experiment",
    "profile_workflow", "push_workflow_to_canvas", "read_image_metadata",
    "read_node_source", "reconstruct_context", "record_experience", "record_outcome",
    "replace_node", "reset_workflow", "rewire_around", "run_pipeline", "save_session",
    "save_workflow", "set_input", "suggest_improvements", "suggest_optimizations",
    "surface_relevant_memory", "swap_model", "undo_workflow_patch",
    "validate_before_execute", "validate_workflow", "verify_execution",
    "watch_outputs_begin", "watch_outputs_diff", "wire_model", "write_image_metadata",
]

MERGE_AWAY = {  # old name -> surviving tool (alias row lands with the merge)
    "analyze_image_cached": "analyze_image",
    "check_registry_freshness": "refresh_registry",
    "create_pipeline": "run_pipeline",
    "execute_with_progress": "execute_workflow",
    "get_civitai_model": "discover",
    "get_execution_profile": "profile_workflow",
    "get_models_summary": "list_models",
    "get_output_path": "verify_execution",
    "get_pipeline_status": "run_pipeline",
    "get_prediction_accuracy": "get_experience_stats",
    "get_repo_releases": "check_node_updates",
    "get_trending_models": "discover",
    "hash_compare_images": "compare_outputs",
    "is_comfyui_running": "comfyui_agent_ping",
    "list_assets": "list_models",
    "list_counterfactuals": "get_experience_stats",
    "list_models_available": "list_models",
    "parse_ui_workflow": "load_workflow",
    "preview_workflow_patch": "apply_workflow_patch",
    "refresh_model_registry": "refresh_registry",
    "suggest_wiring": "wire_model",
}

DELETE = {  # name -> tombstone pointer
    "capture_intent": "internalized: intent capture runs automatically on load/execute",
    "check_evolution_tier": "internalized into agent/loop (MetaAgent dial)",
    "check_subtasks": "removed: the MCP client orchestrates natively",
    "classify_intent": "internalized: routing happens inside iterative_refine",
    "complete_step": "removed: the MCP client plans natively",
    "demo_checkpoint": "removed: demo scaffolding",
    "detect_implicit_feedback": "internalized: runs automatically post-execute",
    "finalize_iterations": "internalized into agent/loop",
    "get_calibration_stats": "internalized into agent/loop",
    "get_current_intent": "internalized: read cozy://session/notes",
    "get_meta_history": "internalized into agent/loop",
    "get_plan": "removed: the MCP client plans natively",
    "plan_goal": "removed: the MCP client plans natively",
    "propose_improvement": "internalized into agent/loop",
    "record_iteration_step": "internalized into agent/loop",
    "replan": "removed: the MCP client plans natively",
    "spawn_subtask": "removed: the MCP client orchestrates natively",
    "start_demo": "removed: demo scaffolding",
    "start_iteration_tracking": "internalized into agent/loop",
    "stage_add_delta": "removed: loop-internal; state visible at cozy://workflow/current",
    "stage_list_deltas": "removed: loop-internal; read cozy://workflow/diff",
    "stage_read": "removed: read cozy://workflow/current",
    "stage_reconstruct_clean": "removed: loop-internal checkpoint API",
    "stage_rollback": "removed: loop-internal checkpoint API",
    "stage_write": "removed: loop-internal checkpoint API",
}

PROVISIONING = {  # the 11-name family -> 5 survivors (4 kept names + provision_node_pack new)
    "repair_workflow": "KEPT (moat: diagnose -> plan -> confirm -> provision)",
    "reconfigure_workflow": "KEPT",
    "provision_model": "KEPT (implementation delegates to comfy-cli)",
    "provision_status": "KEPT (unified status/verify)",
    "download_model": "alias -> provision_model",
    "provision_download": "alias -> provision_model",
    "install_node_pack": "alias -> provision_node_pack (NEW name)",
    "uninstall_node_pack": "alias -> provision_node_pack (DESTRUCTIVE risk class kept)",
    "provision_verify": "alias -> provision_status",
    "provision_pipeline_status": "alias -> provision_status",
    "provision_pipeline_verify": "alias -> provision_status",
}

SCENE_PACK = ["compose_scene", "validate_scene", "extract_conditioning", "export_scene"]
NIM_PACK = ["nim_preflight", "nim_run", "nim_state"]
NEW_NAMES = ["refresh_registry", "provision_node_pack"]


def main() -> int:
    from agent import tools
    registry = sorted(t["name"] for t in tools.ALL_TOOLS)

    buckets = {
        "keep": sorted(KEEP),
        "merge_away": MERGE_AWAY,
        "delete": DELETE,
        "provisioning": PROVISIONING,
        "scene_pack": SCENE_PACK,
        "nim_pack": NIM_PACK,
    }
    flat: list[str] = [*KEEP, *MERGE_AWAY, *DELETE, *PROVISIONING, *SCENE_PACK, *NIM_PACK]

    # --- partition validation: every registered name exactly once ---
    dupes = sorted({n for n in flat if flat.count(n) > 1})
    missing = sorted(set(registry) - set(flat))
    phantom = sorted(set(flat) - set(registry))
    assert not dupes, f"names in more than one bucket: {dupes}"
    assert not missing, f"registered names with no bucket: {missing}"
    assert not phantom, f"bucketed names not in the registry: {phantom}"
    assert len(flat) == len(registry) == 133, (len(flat), len(registry))

    prov_kept = [k for k, v in PROVISIONING.items() if v.startswith("KEPT")]
    core = len(KEEP) + len(prov_kept) + len(NEW_NAMES)
    aliases = len(MERGE_AWAY) + (len(PROVISIONING) - len(prov_kept))
    summary = {
        "registry_total": len(registry),
        "core_listed": core,               # + comfyui_agent_ping (registered outside ALL_TOOLS)
        "scene_pack_gated": len(SCENE_PACK),
        "nim_pack_gated": len(NIM_PACK),
        "alias_rows": aliases,
        "tombstones": len(DELETE),
        "new_names": NEW_NAMES,
        "arithmetic": f"{len(registry)} = {len(KEEP)} keep + {len(MERGE_AWAY)} merge-away "
                      f"+ {len(DELETE)} delete + {len(PROVISIONING)} provisioning "
                      f"+ {len(SCENE_PACK)} scene + {len(NIM_PACK)} nim; "
                      f"core = {len(KEEP)} + {len(prov_kept)} kept-provisioning "
                      f"+ {len(NEW_NAMES)} new = {core} (+ping)",
    }

    (HERE / "census.json").write_text(
        json.dumps({"summary": summary, "buckets": buckets}, indent=1) + "\n", encoding="utf-8")

    lines = ["# v2 Tool Census — strict partition (binding; v2 plan 4.4)", "",
             f"**{summary['arithmetic']}**", "",
             f"Aliases: {aliases} · Tombstones: {len(DELETE)} · "
             f"Gated packs: +{len(SCENE_PACK)} scene (HAS_USD), +{len(NIM_PACK)} nim (podman)", "",
             "| Bucket | Count | Names |", "|---|---|---|"]
    for name, b in buckets.items():
        items = sorted(b) if isinstance(b, (list, tuple)) else sorted(b.keys())
        lines.append(f"| {name} | {len(items)} | {', '.join(items)} |")
    (HERE / "CENSUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
