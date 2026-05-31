/**
 * Surface-report accumulator for write-back v1 delta failures.
 *
 * Every delta the agent emits is either applied to the live ComfyUI
 * canvas or pushed here as a failure entry — never silently dropped
 * (SPEC P3).
 *
 * Consumers:
 *   panel/web/js/superduperPanel.js  → records failures during push
 *   panel/web/js/graphMode.js        → renders failures in the status bar
 *
 * Entry shape:
 *   { type: "tier3_add" | "tier3_delete" | "stale_node_ref" |
 *           "missing_slot" | "malformed" | "link_rejected",
 *     node_id?: string | number,
 *     input_name?: string,
 *     class_type?: string,
 *     raw_value?: any,
 *     reason?: string }
 */

const _entries = [];

export function addDeltaFailure(entry) {
  _entries.push(entry);
}

export function getDeltaFailures() {
  // Return a copy so callers can't mutate the internal array
  return _entries.slice();
}

export function clearDeltaFailures() {
  _entries.length = 0;
}

export function deltaFailureCount() {
  return _entries.length;
}
