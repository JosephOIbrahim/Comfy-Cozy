/**
 * Minimal stub of the ComfyUI / LiteGraph API surface used by
 * pushAgentToCanvas.  Covers only the methods write-back v1 calls; every
 * call is recorded so tests can assert on (call args, call count, order).
 *
 * Production code is host-injected with the real ComfyUI `app` import;
 * tests use vi.mock() to substitute these fakes for the same import path.
 */

export function makeFakeNode(id, opts = {}) {
  const calls = {
    connect: [],
    disconnectInput: [],
    disconnectOutput: [],
  };
  const node = {
    id,
    widgets: opts.widgets ?? [],
    inputs: opts.inputs ?? [],
    outputs: opts.outputs ?? [],
    color: undefined,
    connect(outputSlot, targetNode, targetSlot) {
      calls.connect.push({ outputSlot, targetNode, targetSlot });
      return true;
    },
    disconnectInput(slot) {
      calls.disconnectInput.push(slot);
      return true;
    },
    disconnectOutput(slot, targetNode) {
      calls.disconnectOutput.push({ slot, targetNode });
      return true;
    },
    _calls: calls,
  };
  return node;
}

export function makeFakeGraph(nodesById = {}) {
  let _onAfterChange = null;
  const calls = {
    removeLink: [],
  };
  return {
    _nodesById: nodesById,
    get onAfterChange() {
      return _onAfterChange;
    },
    set onAfterChange(fn) {
      _onAfterChange = fn;
    },
    getNodeById(id) {
      return nodesById[id] ?? null;
    },
    removeLink(linkId) {
      calls.removeLink.push(linkId);
    },
    serialize() {
      // Tests can override; default returns the node set.
      return { nodes: Object.values(nodesById) };
    },
    _calls: calls,
  };
}

export function makeFakeApp(graph) {
  const g = graph ?? makeFakeGraph();
  return {
    graph: g,
    canvas: {
      setDirty() {
        /* no-op for tests */
      },
    },
    graphToPrompt() {
      return Promise.resolve({ output: {} });
    },
  };
}
