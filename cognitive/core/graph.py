"""CognitiveGraphEngine — LIVRPS composition engine.

Manages a base workflow and a stack of delta layers. Resolution
applies deltas weakest-to-strongest (last write wins = strongest
opinion wins). Link arrays are never modified unless explicitly
targeted by a mutation.
"""

from __future__ import annotations

import copy
import threading
from typing import Any

from .delta import DeltaLayer, LIVRPS_PRIORITY, Opinion
from .models import WorkflowGraph


_MAX_DELTA_STACK = 1_000  # FIFO eviction cap (Cycle 39)


class CognitiveGraphEngine:
    """Non-destructive workflow mutation engine with LIVRPS composition.

    The engine holds a frozen base workflow and a stack of delta layers.
    Resolution produces a new WorkflowGraph by applying deltas in
    priority order (weakest first, strongest last = strongest wins).
    """

    def __init__(self, base_workflow_data: dict[str, Any]):
        """Initialize with raw ComfyUI API JSON.

        Args:
            base_workflow_data: ComfyUI API format dict
                {node_id: {"class_type": ..., "inputs": {...}}, ...}
        """
        self._base = WorkflowGraph.from_api_json(base_workflow_data)
        self._base_raw = copy.deepcopy(base_workflow_data)
        self._delta_stack: list[DeltaLayer] = []
        self._max_delta_stack = _MAX_DELTA_STACK
        self._delta_stack_lock = threading.Lock()  # Guards all _delta_stack mutations

    @property
    def base(self) -> WorkflowGraph:
        """The frozen base workflow (never mutated)."""
        return self._base

    @property
    def delta_stack(self) -> list[DeltaLayer]:
        """Defensive copy of the delta stack (snapshot under lock)."""
        with self._delta_stack_lock:
            return list(self._delta_stack)

    def mutate_workflow(
        self,
        mutations: dict[str, dict[str, Any]],
        opinion: Opinion = "L",
        layer_id: str | None = None,
        description: str = "",
    ) -> DeltaLayer:
        """Create and push a new delta layer.

        Args:
            mutations: {node_id: {param: value, ...}, ...}
                If a node_id is not in the base graph and "class_type"
                is present in the mutation dict, the node is injected.
            opinion: LIVRPS tier for this mutation.
            layer_id: Optional explicit layer ID.
            description: Human-readable description.

        Returns:
            The created DeltaLayer.
        """
        delta = DeltaLayer.create(
            mutations=mutations,
            opinion=opinion,
            layer_id=layer_id,
            description=description,
        )
        with self._delta_stack_lock:
            self._delta_stack.append(delta)
            if len(self._delta_stack) > self._max_delta_stack:  # Cycle 39: FIFO eviction
                self._delta_stack.pop(0)
        return delta

    def get_resolved_graph(self, up_to_index: int | None = None) -> WorkflowGraph:
        """Resolve base + deltas into a single WorkflowGraph.

        Resolution order:
        1. Deep copy base workflow (raw dict for maximum fidelity)
        2. Sort deltas by LIVRPS priority (stable sort preserves
           chronological order for same-priority layers)
        3. Apply mutations weakest-to-strongest (strongest writes last = wins)
        4. For each mutation: update only specified keys in node inputs,
           preserving all other inputs and link arrays
        5. If mutation references a node not in base AND includes class_type:
           inject as new node

        Args:
            up_to_index: If provided, only consider deltas[0:up_to_index]
                in the original insertion order.
        """
        resolved = self._resolve_from_raw(up_to_index)
        return WorkflowGraph.from_api_json(resolved)

    def _resolve_from_raw(self, up_to_index: int | None = None) -> dict[str, Any]:
        """Internal resolution on raw dicts for maximum link fidelity."""
        result = copy.deepcopy(self._base_raw)

        with self._delta_stack_lock:
            deltas = list(self._delta_stack[:up_to_index])  # Snapshot under lock

        # Stable sort by LIVRPS priority: same priority preserves insertion order
        sorted_deltas = sorted(deltas, key=lambda d: d.priority)

        for delta in sorted_deltas:
            for node_id, params in delta.mutations.items():
                if node_id in result:
                    # Existing node: update only specified input keys
                    node = result[node_id]
                    inputs = node.setdefault("inputs", {})
                    for param_name, param_value in params.items():
                        if param_name == "class_type":
                            continue
                        inputs[param_name] = copy.deepcopy(param_value)
                else:
                    # New node injection: requires class_type
                    if "class_type" in params:
                        new_inputs = {
                            k: copy.deepcopy(v)
                            for k, v in params.items()
                            if k != "class_type"
                        }
                        result[node_id] = {
                            "class_type": params["class_type"],
                            "inputs": new_inputs,
                        }

        return result

    def verify_stack_integrity(self) -> tuple[bool, list[str]]:
        """Check all delta layers for tampering.

        Returns:
            (all_intact, list_of_error_messages)
            Empty error list when all layers are intact.
        """
        errors = []
        with self._delta_stack_lock:
            snapshot = list(self._delta_stack)
        for delta in snapshot:
            if not delta.is_intact:
                errors.append(
                    f"Layer {delta.layer_id!r} (opinion={delta.opinion}) "
                    f"has been tampered with: creation_hash != current hash"
                )
        return (len(errors) == 0, errors)

    def temporal_query(self, back_steps: int = 1) -> WorkflowGraph:
        """Get the resolved graph at a previous point in time.

        Args:
            back_steps: Number of delta layers to exclude from the top.
                1 = exclude last delta, 2 = exclude last two, etc.
                0 or negative = return current resolved graph.

        Returns:
            WorkflowGraph resolved with only the older deltas.
        """
        if back_steps <= 0:
            return self.get_resolved_graph()
        with self._delta_stack_lock:
            stack_len = len(self._delta_stack)
        idx = max(0, stack_len - back_steps)
        return self.get_resolved_graph(up_to_index=idx)

    def pop_delta(self) -> DeltaLayer | None:
        """Remove and return the most recent delta layer.

        Returns None if the stack is empty.
        """
        with self._delta_stack_lock:
            if self._delta_stack:
                return self._delta_stack.pop()
        return None

    def compact_stack(self) -> int:
        """Collapse maximal runs of consecutive same-opinion deltas into one.

        An explicit, opt-in cleanup for long sessions: it bounds delta-stack
        growth more intelligently than the FIFO eviction cap by merging a
        burst of successive same-opinion edits (e.g. many Local tweaks) into a
        single layer.

        Resolution-preserving. Same-opinion deltas resolve in insertion order
        with last-write-wins per key (see ``_resolve_from_raw``), so the
        key-wise merge of a *contiguous* same-opinion run yields the identical
        resolved graph — while shrinking the stack.

        Trade-off: compaction discards the fine-grained history *within* a
        collapsed run, so ``temporal_query`` / ``pop_delta`` can no longer step
        through those individual edits. That is why it is opt-in, not
        automatic. A run containing a tampered layer (``is_intact`` False) is
        left untouched, so a fresh merge hash never hides tamper detection.

        Returns:
            The number of layers removed (0 if nothing was compacted).
        """
        with self._delta_stack_lock:
            original = self._delta_stack
            if len(original) < 2:
                return 0
            compacted: list[DeltaLayer] = []
            i, n = 0, len(original)
            while i < n:
                j = i + 1
                while j < n and original[j].opinion == original[i].opinion:
                    j += 1
                run = original[i:j]
                if (
                    len(run) > 1
                    and all(d.is_intact for d in run)
                    and self._run_is_mergeable(run)
                ):
                    compacted.append(self._merge_run(run))
                else:
                    compacted.extend(run)
                i = j
            removed = len(original) - len(compacted)
            if removed:
                self._delta_stack = compacted
            return removed

    @staticmethod
    def _merge_run(run: list[DeltaLayer]) -> DeltaLayer:
        """Merge a contiguous same-opinion run into one delta.

        Non-class_type keys are last-wins (later mutations overwrite earlier
        per (node_id, key)). ``class_type`` is FIRST-wins per node, mirroring
        resolution: injection pins an injected node's class_type at its first
        appearance and skips class_type on every later update to that node
        (``_resolve_from_raw`` line ``if param_name == "class_type": continue``).
        Merging class_type last-wins would silently flip an injected node's
        type — caught by adversarial review.
        """
        merged: dict[str, dict[str, Any]] = {}
        for delta in run:
            for node_id, params in delta.mutations.items():
                node = merged.setdefault(node_id, {})
                for key, value in params.items():
                    if key == "class_type" and "class_type" in node:
                        continue  # first class_type wins (mirrors injection)
                    node[key] = copy.deepcopy(value)
        return DeltaLayer.create(
            mutations=merged,
            opinion=run[0].opinion,
            description=f"compacted {len(run)} {run[0].opinion} layers",
        )

    @staticmethod
    def _run_is_mergeable(run: list[DeltaLayer]) -> bool:
        """True if merging this same-opinion run cannot change resolution.

        The one unsafe pattern is an *orphan* mutation: a node whose FIRST
        appearance in the run sets params WITHOUT class_type, while a LATER
        delta in the run supplies its class_type. Resolution drops those
        pre-injection params (a mutation to a not-yet-present node without
        class_type is a no-op), but a naive key-wise merge would resurrect
        them. In that case, refuse to merge and keep the run verbatim.
        """
        seen: set[str] = set()
        seen_without_ct: set[str] = set()
        for delta in run:
            for node_id, params in delta.mutations.items():
                has_ct = "class_type" in params
                if node_id not in seen:
                    seen.add(node_id)
                    if not has_ct:
                        seen_without_ct.add(node_id)
                elif has_ct and node_id in seen_without_ct:
                    return False
        return True

    def __deepcopy__(self, memo: dict) -> "CognitiveGraphEngine":
        """Support copy.deepcopy() — creates a fresh lock, copies data.

        threading.Lock() cannot be pickled or deep-copied, so we must
        implement __deepcopy__ explicitly (same pattern as WorkflowSession).
        The new engine gets its own independent lock.
        """
        with self._delta_stack_lock:
            new = CognitiveGraphEngine.__new__(CognitiveGraphEngine)
            new._base = copy.deepcopy(self._base, memo)
            new._base_raw = copy.deepcopy(self._base_raw, memo)
            new._delta_stack = copy.deepcopy(self._delta_stack, memo)
            new._max_delta_stack = self._max_delta_stack
            new._delta_stack_lock = threading.Lock()
            return new

    def to_api_json(self) -> dict[str, Any]:
        """Get the fully resolved workflow as ComfyUI API JSON.

        This is the primary output method — returns a dict ready to
        submit to ComfyUI's /prompt endpoint.
        """
        return self._resolve_from_raw()
