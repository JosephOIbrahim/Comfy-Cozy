#!/usr/bin/env python3
"""R2R triage: deterministic policy classifier for review findings.

FINDINGS.json carries *facts* about each finding (which seams it touches, whether
it pulls a dep, etc.). This module applies *policy* -- it derives (tier, consent,
dispatch) from those facts using explicit rules, never heuristics. Same input ->
same output, always (He2025 determinism: sorted, no clocks, no randomness).

The rules encode ORCHESTRATOR_v2's authority model so that the build-layer consent
asymmetry mirrors the product's (edits act, fetches ask):

  touches accept-authority / gate-model  -> Tier C, Joe file-by-file (s10: recursion stops at the judge)
  touches frozen stage (agent/stage/**)  -> gated behind G8 unfreeze
  network/install OR undeclared new dep  -> gated behind G4
  already covered by an existing track   -> link-existing (dedup, NOT a new epoch)
  positioning doc change                 -> Tier B, Joe-reviewed PR
  otherwise                              -> Tier A autonomous epoch

Usage:
    python triage.py                 # print the triage plan for FINDINGS.json
    python triage.py --json          # machine-readable plan to stdout
    python triage.py --selftest      # assert the boundary cases (exit non-zero on fail)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FINDINGS_PATH = Path(__file__).with_name("FINDINGS.json")

# Tiers (ORCHESTRATOR_v2 s10)
TIER_A = "A"  # autonomous: product/test/doc-hygiene
TIER_B = "B"  # self-tuning, Joe-reviewed PR (evals, positioning, priorities)
TIER_C = "C"  # never autonomous: accept authority / consent model


def triage(f: dict) -> dict:
    """Pure function: finding facts -> (tier, consent, dispatch, gate). Deterministic."""
    # Order matters: strongest constraint wins first (fail-closed toward more gating).
    if f.get("touches_accept_authority") or f.get("touches_gate_model"):
        return _v(TIER_C, "joe-review", "tier-c-review", "G7",
                  "edits the accept authority or consent model; recursion stops at the judge")
    if f.get("touches_frozen_stage"):
        return _v(TIER_A, "gated-unfreeze", "needs-unfreeze", "G8",
                  "touches agent/stage/** frozen zone")
    if f.get("network_or_install") or f.get("new_import"):
        return _v(TIER_A, "gated-fetch", "autonomous-after-g4", "G4",
                  "pulls code / a possibly-undeclared dependency")
    # Positioning beats dedup: a claims/positioning change gets Joe's review even
    # when it mechanically rides an existing hygiene lane (in_program_ref).
    if f.get("positioning"):
        return _v(TIER_B, "autonomous-edit", "epoch", None,
                  "positioning/claims change -> Joe-reviewed PR")
    if f.get("in_program_ref"):
        return _v(TIER_A, "n/a", "link-existing", None,
                  "already covered: " + str(f["in_program_ref"]))
    if f.get("class") in ("doc", "self"):
        return _v(TIER_A, "autonomous-edit", "epoch", None, "hygiene/self, autonomous")
    return _v(TIER_A, "autonomous-edit", "epoch", None, "product change, autonomous")


def _v(tier, consent, dispatch, gate, why):
    return {"tier": tier, "consent": consent, "dispatch": dispatch, "gate": gate, "why": why}


def load_findings(path: Path = FINDINGS_PATH) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["findings"]


def plan(findings: list[dict]) -> list[dict]:
    """Attach triage verdicts; return rows sorted by (wave, id) deterministically."""
    rows = []
    for f in findings:
        v = triage(f)
        rows.append({
            "id": f["id"], "title": f["title"], "size": f.get("size"),
            "wave": f.get("wave"), "golden": bool(f.get("golden")),
            "verified": bool(f.get("verified")), "depends_on": f.get("depends_on", []),
            **v,
        })
    # wave None (linked/parked) sorts last; then by wave, then id.
    return sorted(rows, key=lambda r: (r["wave"] is None, r["wave"] or 0, r["id"]))


def render(rows: list[dict]) -> str:
    out = ["R2R triage plan  (dispatch order: wave, then id)", "=" * 68]
    for r in rows:
        gold = "  [GOLDEN]" if r["golden"] else ""
        wave = "link" if r["wave"] is None else f"W{r['wave']}"
        gate = f" gate={r['gate']}" if r["gate"] else ""
        dep = f" deps={','.join(r['depends_on'])}" if r["depends_on"] else ""
        ver = "" if r["verified"] else "  (Scout-unverified)"
        out.append(f"{r['id']}  {wave} tier={r['tier']} consent={r['consent']} "
                   f"-> {r['dispatch']}{gate}{gold}")
        out.append(f"     {r['title']}{dep}{ver}")
        out.append(f"     policy: {r['why']}")
    return "\n".join(out)


# --- self-test: the boundary cases the harness must never get wrong ----------

def _selftest() -> int:
    fails = []

    def expect(name, got, want):
        if got != want:
            fails.append(f"{name}: got {got!r} want {want!r}")

    real = {f["id"]: triage(f) for f in load_findings()}
    # Live findings from this review:
    expect("F-01 autonomous", real["F-01"]["dispatch"], "epoch")
    expect("F-01 consent", real["F-01"]["consent"], "autonomous-edit")
    expect("F-02 dep-gated", real["F-02"]["gate"], "G4")            # new_import -> G4
    expect("F-03 dedup", real["F-03"]["dispatch"], "link-existing")  # in_program_ref
    expect("F-05 golden-autonomous", real["F-05"]["dispatch"], "epoch")
    expect("F-08 gate-model->tier-C", real["F-08"]["tier"], TIER_C)  # touches_gate_model
    expect("F-08 joe-review", real["F-08"]["consent"], "joe-review")
    expect("F-11 positioning->tier-B", real["F-11"]["tier"], TIER_B)

    # Synthetic boundary probes (the asymmetry must hold for any future finding):
    expect("install->G4", triage({"network_or_install": True})["gate"], "G4")
    expect("accept-authority->tier-C",
           triage({"touches_accept_authority": True})["tier"], TIER_C)
    expect("frozen-stage->G8",
           triage({"touches_frozen_stage": True})["gate"], "G8")
    # Precedence: accept-authority beats install (strongest constraint wins).
    expect("precedence",
           triage({"touches_accept_authority": True, "network_or_install": True})["tier"],
           TIER_C)

    if fails:
        print("SELFTEST FAILED:")
        for x in fails:
            print("  -", x)
        return 1
    print(f"SELFTEST OK  ({len(real)} findings triaged, boundary probes green)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="R2R triage classifier")
    ap.add_argument("--json", action="store_true", help="machine-readable plan")
    ap.add_argument("--selftest", action="store_true", help="assert boundary cases")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    rows = plan(load_findings())
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print(render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
