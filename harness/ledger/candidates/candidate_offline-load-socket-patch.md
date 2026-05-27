---
candidate: prove-no-network-via-socket-patch
goal: Guarantee a model-backed ingest path makes zero network calls in default config
verifier_outcome: PASS (socket-patch property test green with NO HF_HUB_OFFLINE crutch)
similar_to: []
created: 2026-05-27
consolidated_from: 1
---

## Goal
Satisfy "no outbound network during ingest" (SPEC P4) for a HuggingFace-backed
embedder whose first load would otherwise fetch weights.

## Approach
1. Split install-time vs runtime: an explicit `provision_model()` is the ONE
   sanctioned download; the ingest load path uses `local_files_only=True`.
   A cache miss then raises loudly rather than silently fetching.
2. Verify with a socket-patch property test: monkeypatch `socket.socket.connect`
   AND `socket.getaddrinfo` to raise; reset the model singleton so the *load*
   path runs under the block; assert ingest completes with zero attempts.
3. Run the test WITHOUT `HF_HUB_OFFLINE` set — proves the code (local_files_only)
   guarantees offline, not an ambient env var.

## Verifier
L2 property test (socket egress == 0 during bge ingest).

## Anti-patterns
- Relying on `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` env as the guarantee (ambient,
  not enforced by the artifact).
- Patching only `connect` (misses DNS via getaddrinfo).
- Testing encode-only without resetting the singleton (skips the load path).
