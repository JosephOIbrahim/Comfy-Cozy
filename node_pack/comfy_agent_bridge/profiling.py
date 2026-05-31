"""Per-node execution timing capture (#5) for comfy_agent_bridge.

Pure logic — NO ComfyUI imports — so it is unit-testable in isolation. The
package __init__ wires this to PromptServer.send_sync (observing the
execution_start / executing / executed / execution_cached / execution_success
events ComfyUI already broadcasts) and exposes it at
GET /agent/exec_profile/{prompt_id}.

VRAM GATE (Leg 0): the WS stream carries no vram/memory data, so this is
DURATION-ONLY, measured consumer-side via a monotonic clock. class_type is not
present in the executing/executed events and is left None (the executing event
payload is {node, display_node, prompt_id}); the agent-side tool tolerates it.
"""

from collections import OrderedDict

_MAX_PROMPTS = 32  # bounded ring of recent prompts (no unbounded growth)


class TimingCapture:
    """Accumulate per-node durations from ComfyUI execution events.

    clock: zero-arg callable returning seconds (e.g. time.perf_counter).
    """

    def __init__(self, clock):
        self._clock = clock
        self._profiles: "OrderedDict[str, dict]" = OrderedDict()

    def _prof(self, pid: str) -> dict:
        p = self._profiles.get(pid)
        if p is None:
            p = {"nodes": [], "_open": None}
            self._profiles[pid] = p
            self._profiles.move_to_end(pid)
            while len(self._profiles) > _MAX_PROMPTS:
                self._profiles.popitem(last=False)
        return p

    def _close_open(self, prof: dict, now: float) -> None:
        if prof["_open"] is not None:
            nid, start = prof["_open"]
            prof["nodes"].append({
                "node_id": nid,
                "class_type": None,
                "start": start,
                "duration_ms": round((now - start) * 1000.0, 2),
            })
            prof["_open"] = None

    def observe(self, event: str, data) -> None:
        if not isinstance(data, dict):
            return
        pid = data.get("prompt_id")
        if not pid:
            return
        if event == "execution_start":
            prof = self._prof(pid)
            prof["nodes"].clear()
            prof["_open"] = None
        elif event == "execution_cached":
            prof = self._prof(pid)
            for nid in data.get("nodes", []) or []:
                prof["nodes"].append({
                    "node_id": nid,
                    "class_type": None,
                    "start": 0.0,
                    "duration_ms": 0.0,
                    "cached": True,
                })
        elif event == "executing":
            prof = self._prof(pid)
            now = self._clock()
            self._close_open(prof, now)
            node = data.get("node")
            if node is not None:
                prof["_open"] = (node, now)
        elif event in ("execution_success", "execution_error"):
            prof = self._prof(pid)
            self._close_open(prof, self._clock())

    def profile(self, pid: str):
        prof = self._profiles.get(pid)
        if prof is None:
            return None
        return {"prompt_id": pid, "nodes": list(prof["nodes"])}
