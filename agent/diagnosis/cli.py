"""`agent diagnose` — the keyless terminal surface. Deterministic code only;
no LLM, no API key, anywhere in this path (DISPATCH D1).

Exit codes: 0 = rendered · 1 = --strict and a critical finding exists · 2 = no document.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .diagnosis import canonical_json, load_baseline, recent_paths, workflow_hash

_SEV_STYLE = {"info": "cyan", "warn": "yellow", "critical": "bold red"}


def _find_doc(whash: str | None = None, diagnosis_id: str | None = None,
              prompt_id: str | None = None) -> dict | None:
    """Newest document matching the given key (all keys None -> newest overall)."""
    for p in recent_paths():
        try:
            doc = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if whash and doc.get("run", {}).get("workflowHash") != whash:
            continue
        if diagnosis_id and doc.get("diagnosisId") != diagnosis_id:
            continue
        if prompt_id and doc.get("run", {}).get("promptId") != prompt_id:
            continue
        return doc
    return None


def render(doc: dict, console: Console) -> None:
    env, run = doc["env"], doc["run"]
    baseline = load_baseline(doc["envHash"], run["workflowHash"])
    console.print(
        f"[bold]env {doc['envHash'][:8]}[/bold] · {doc['nodeId']} · {doc['createdAt']}\n"
        f"  {env['os']} · python {env['python']} · torch {env['torch']} "
        f"({env['torchCuda']}) · driver {env['driver']} · ComfyUI {env['comfyuiVersion']}"
    )
    status_style = "green" if run["status"] == "completed" else "bold red"
    console.print(
        f"run [{status_style}]{run['status']}[/{status_style}] · {run['durationS']:.1f}s · "
        f"workflow {run['workflowHash'][:8]} · baseline {baseline['runCount']} clean "
        f"run{'s' if baseline['runCount'] != 1 else ''}"
    )
    if run["stages"]:
        table = Table(title=None, show_edge=False, pad_edge=False)
        table.add_column("stage")
        table.add_column("ms", justify="right")
        for s in run["stages"]:
            table.add_row(s["stage"], f"{s['ms']:.0f}")
        console.print(table)
    else:
        console.print("  [dim]no per-node timing (bridge not installed) — stages: [][/dim]")
    console.print(f"triggers: {', '.join(doc['triggers']) if doc['triggers'] else '[green]none[/green]'}")
    if doc["findings"]:
        for f in doc["findings"]:
            style = _SEV_STYLE.get(f["severity"], "white")
            console.print(f"  [{style}]{f['severity'].upper()}[/{style}] {f['code']} — {f['explanation']}")
            if f.get("fixHint"):
                console.print(f"    [dim]fix:[/dim] {f['fixHint']}")
    else:
        console.print("findings: [green]none — every gap explained, nothing fired[/green]")


def _assert_env(expected: str, console: Console, as_json: bool) -> int:
    """Assert the box's environment fingerprint still matches a recorded hash —
    'we use the tool to protect the demo of the tool'. Prefers a FRESH worker
    reading (has the box drifted?), falls back to the last report when the worker
    is unreachable. Exit 0 = match · 3 = drift · 2 = can't determine. Keyless."""
    from .diagnosis import collect_env, env_hash
    expected = expected.strip().lower()
    try:
        actual = env_hash(collect_env())
        source = "live worker"
    except Exception:
        doc = _find_doc()
        if not doc:
            msg = "cannot assert env: worker unreachable and no prior report on disk"
            print(json.dumps({"error": msg})) if as_json else console.print(f"[yellow]{msg}[/yellow]")
            return 2
        actual = doc["envHash"]
        source = "last report"
    match = actual == expected
    if as_json:
        print(json.dumps({"assertEnv": expected, "actual": actual, "match": match, "source": source}))
    elif match:
        console.print(f"[green]✓ env matches {expected[:8]}[/green] — unchanged since recorded ({source})")
    else:
        console.print(f"[bold red]✗ env DRIFTED[/bold red] — recorded {expected[:8]}, "
                      f"now {actual[:8]} ({source}). The box is not the one you froze.")
    return 0 if match else 3


def run_diagnose(workflow: str | None = None, last: bool = False,
                 as_json: bool = False, strict: bool = False,
                 assert_env: str | None = None) -> int:
    console = Console()
    if assert_env:
        return _assert_env(assert_env, console, as_json)
    whash = None
    if workflow and not last:
        try:
            whash = workflow_hash(json.loads(Path(workflow).read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            if as_json:
                print(json.dumps({"error": f"could not read workflow file: {e}"}))
            else:
                console.print(f"[red]Could not read workflow file:[/red] {e}")
            return 2
    doc = _find_doc(whash=whash)
    if doc is None:
        hint = ("no diagnosis matches that workflow (documents key on the resolved graph "
                "that actually ran)" if whash else
                "no diagnosis documents yet — run a workflow first; reports land automatically")
        if as_json:
            print(json.dumps({"error": hint}))  # stdout stays JSON-pure for pipes (D1 beat)
        else:
            console.print(f"[yellow]{hint}[/yellow]")
        return 2
    if as_json:
        print(canonical_json(doc))
    else:
        render(doc, console)
    if strict and any(f["severity"] == "critical" for f in doc["findings"]):
        return 1
    return 0


def query(q: str = "latest") -> str:
    """The ONE MCP read surface (Cherny cut #5): latest | env | <diagnosisId> | <promptId>."""
    q = (q or "latest").strip()
    if q == "latest":
        doc = _find_doc()
        return canonical_json(doc) if doc else json.dumps({"error": "no diagnosis documents yet"})
    if q == "env":
        doc = _find_doc()
        if not doc:
            return json.dumps({"error": "no diagnosis documents yet"})
        open_findings = []
        for p in recent_paths(50):
            d = _safe_doc(p)
            if d.get("envHash") == doc["envHash"]:
                open_findings.extend(f for f in d.get("findings", [])
                                     if f.get("severity") in ("warn", "critical"))
        return canonical_json({"envHash": doc["envHash"], "env": doc["env"],
                               "openFindings": open_findings[:20]})
    doc = _find_doc(diagnosis_id=q) or _find_doc(prompt_id=q)
    return canonical_json(doc) if doc else json.dumps({"error": f"no diagnosis matches {q!r}"})


def _safe_doc(p: Path) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
