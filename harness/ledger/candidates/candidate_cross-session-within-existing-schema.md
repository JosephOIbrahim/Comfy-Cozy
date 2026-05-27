---
candidate: inject-into-consumer-without-touching-it
goal: Add new data to a consumer-owned artifact without modifying the (NO-TOUCH) consumer
verifier_outcome: PASS (cross-repo load via the real consumer; cross-session memory visible)
similar_to: []
created: 2026-05-27
consolidated_from: 1
---

## Goal
Fold cross-session memories into the capsule the consumer auto-loads, when the
consumer repo (Comfy-Cozy `session.py`) is constitutionally NO-TOUCH.

## Approach
1. First verify the existing artifact schema the consumer reads (notes =
   list[{text,type,added_at}], typed v2). Confirm the new data fits as
   existing-type entries — encode provenance in the `text`, add NO new field.
2. If it cannot fit existing schema → HALT + escalate (would require touching
   the consumer). Here it fit, so no escalation.
3. Make injection best-effort: wrap the cross-source call in try/except so the
   primary artifact still writes if the addition fails. Isolate the failure.
4. Prove it with the consumer's REAL loader (cross-repo import), not just a
   structural assert — load the generated artifact and confirm the new data is
   visible after the consumer's own normalize/migrate.

## Verifier
L1 e2e (memory from session A appears in session B's capsule) + L3 (real
consumer `load_session` accepts it, schema_version intact).

## Anti-patterns
- Adding a new field the consumer doesn't read (silent drop / forces consumer change).
- Letting a cross-source retrieval failure abort the primary write.
- Asserting only structure without loading through the real consumer.
