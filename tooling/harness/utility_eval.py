#!/usr/bin/env python
"""utility_eval.py — golden-task utility scoreboard (Utility Track U0, seed set).

Measures what verify_ratchet cannot: did the artist get helped? Each scenario
drives the REAL MCP dispatch surface (agent.tools.handle) end-to-end and scores
0/1 on outcome assertions, recording per-scenario dispatch latency. Deterministic:
the U0 seed set needs no ComfyUI server, no API key, no network (U1 adds
mocked-HTTP classes: discovery, repair funnel, vision).

Output: tooling/harness/v2/utility_score.json
  {scenarios: {id: {score, latency_ms, detail}}, score, scenario_count}

Becomes ratchet check #8 (score >= baseline - band; scenario_count only ratchets
UP — the eval-gaming tripwire; per-scenario latency vs champion, 1.25x band).
Tier B of the recursion contract: changes here are evidence-cited, Joe-reviewed.

Exit codes: 0 ran (score in JSON), 2 harness error. Stdlib only.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "tooling" / "harness" / "v2" / "utility_score.json"

# Minimal SD1.5 API-format workflow — the shape every scenario starts from.
SAMPLE_WORKFLOW = {
    "1": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "sd15_base.safetensors"}},
    "2": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "a cozy cabin", "clip": ["1", 1]}},
    "3": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "blurry", "clip": ["1", 1]}},
    "4": {"class_type": "EmptyLatentImage",
          "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    "5": {"class_type": "KSampler",
          "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                     "latent_image": ["4", 0], "seed": 42, "steps": 20, "cfg": 8.0,
                     "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
    "6": {"class_type": "VAEDecode",
          "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
    "7": {"class_type": "SaveImage",
          "inputs": {"images": ["6", 0], "filename_prefix": "utility_eval"}},
}


def _handle(name: str, tool_input: dict) -> dict | list | str:
    """Dispatch through the real surface; tolerate JSON-string or dict returns."""
    from agent import tools
    raw = tools.handle(name, tool_input)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _load_sample() -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump(SAMPLE_WORKFLOW, f)
        path = f.name
    return _handle("load_workflow", {"file_path": path})


def _current_ksampler() -> dict:
    """Read the live session workflow's KSampler inputs via the diff-free path."""
    from agent.tools import workflow_patch
    state = workflow_patch._get_state()
    wf = state.get("current_workflow") or {}
    return (wf.get("5") or {}).get("inputs", {})


# ---------------------------------------------------------------------------
# Scenarios — each returns (passed: bool, detail: str)
# ---------------------------------------------------------------------------

def scenario_intent_dreamier() -> tuple[bool, str]:
    """'Make it dreamier' via the zero-LLM recipe layer: CFG must drop, steps
    must not decrease (CLAUDE.md artistic-intent table)."""
    _load_sample()
    before = dict(_current_ksampler())
    recipes = _handle("list_recipes", {})
    text = json.dumps(recipes).lower()
    if "dream" not in text:
        return False, "no dreamier-class recipe registered"
    result = _handle("apply_recipe", {"intent": "dreamier"})
    if isinstance(result, dict) and result.get("error"):
        result = _handle("apply_recipe", {"name": "dreamier"})
    after = _current_ksampler()
    cfg_drop = float(after.get("cfg", 99)) < float(before.get("cfg", 0))
    steps_ok = int(after.get("steps", 0)) >= int(before.get("steps", 99))
    return (cfg_drop and steps_ok,
            f"cfg {before.get('cfg')} -> {after.get('cfg')}, "
            f"steps {before.get('steps')} -> {after.get('steps')}")


def scenario_provision_gate() -> tuple[bool, str]:
    """Code-executing installs must surface a confirmation gate, never run."""
    result = _handle("install_node_pack", {"pack_name": "definitely-not-installed-pack"})
    text = json.dumps(result).lower()
    gated = ("needs_confirmation" in text or "confirm" in text) and "cloned" not in text
    return gated, f"gate response: {str(result)[:160]}"


def scenario_compat_refusal() -> tuple[bool, str]:
    """SD1.5 LoRA on an SDXL checkpoint: refuse, and explain like a colleague."""
    result = _handle("check_model_compatibility", {
        "checkpoint": "sdxl_base_1.0.safetensors",
        "lora": "sd15_detail_lora.safetensors",
    })
    text = json.dumps(result).lower()
    refused = ("incompatible" in text or "not compatible" in text
               or ("sdxl" in text and "sd1" in text and "mix" in text))
    humane = "traceback" not in text
    return refused and humane, f"verdict: {str(result)[:160]}"


def scenario_undo_roundtrip() -> tuple[bool, str]:
    """Edit -> visible diff -> undo -> clean. The safety story artists rely on."""
    _load_sample()
    _handle("set_input", {"node_id": "5", "field": "cfg", "value": 3.5})
    after_edit = _current_ksampler()
    if float(after_edit.get("cfg", 0)) != 3.5:
        return False, f"edit did not land: cfg={after_edit.get('cfg')}"
    diff = _handle("get_workflow_diff", {})
    diff_text = json.dumps(diff)
    if "cfg" not in diff_text and "3.5" not in diff_text:
        return False, "diff does not show the edit"
    _handle("undo_workflow_patch", {})
    after_undo = _current_ksampler()
    return (float(after_undo.get("cfg", 0)) == 8.0,
            f"cfg 8.0 -> 3.5 -> {after_undo.get('cfg')} after undo")


def scenario_error_humanity() -> tuple[bool, str]:
    """A wrong node id must produce a human explanation, not machinery."""
    _load_sample()
    result = _handle("set_input", {"node_id": "999", "field": "cfg", "value": 1.0})
    text = json.dumps(result)
    has_error = "error" in text.lower() or "not found" in text.lower()
    no_traceback = "Traceback" not in text and "raise " not in text
    mentions_node = "999" in text or "node" in text.lower()
    return has_error and no_traceback and mentions_node, f"error shape: {text[:160]}"


SCENARIOS = {
    "intent-dreamier": scenario_intent_dreamier,
    "provision-gate": scenario_provision_gate,
    "compat-refusal": scenario_compat_refusal,
    "undo-roundtrip": scenario_undo_roundtrip,
    "error-humanity": scenario_error_humanity,
}


def main() -> int:
    results = {}
    for sid, fn in SCENARIOS.items():
        t0 = time.perf_counter()
        try:
            passed, detail = fn()
        except Exception as e:  # a crashing scenario scores 0, never kills the run
            passed, detail = False, f"scenario raised: {type(e).__name__}: {e}"
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        results[sid] = {"score": 1 if passed else 0,
                        "latency_ms": latency_ms, "detail": detail}
        print(f"  {'PASS' if passed else 'FAIL'}  {sid:18s} {latency_ms:8.1f} ms  {detail}")
    score = round(sum(r["score"] for r in results.values()) / len(results), 3)
    out = {"scenarios": results, "score": score, "scenario_count": len(results)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"utility score: {score} ({sum(r['score'] for r in results.values())}/{len(results)}) -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
