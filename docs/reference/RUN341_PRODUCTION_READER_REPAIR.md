# Run341 Production Reader Repair

## Evidence that triggered the change

The 2026-09-10 full Daily completed successfully but produced 0 Ready articles from 3 Deep Dive attempts. Two generated manuscripts exposed a repeatable Reader Value failure mode.

- DeepSeek v4.1 Flash: Publication Readiness passed, but Human Appeal was WEAK. A mixed HARD factual retry improved the `what` surface while the `why` and `decision` reader scores regressed; final deterministic subtraction exceeded the information-loss limit and correctly refused Ready.
- IBIB: factual/source/publication checks passed, but `multi_axis_reader_weakness` and `non_engineer_access_failure` remained. Normal Production deliberately returned `reader_value_review_no_retry`, so no repair attempt was authorized.

These observations falsify a model-only explanation. The control policy itself was preventing a repair for reader-only failures, while the mixed HARD patch contract was too narrow to reliably restore reader flow.

## Production contract

Run341 does not lower any quality threshold and adds no independent retry loop.

1. **Reader Path on first generation**
   - Open in plain Japanese with: what changed / why it matters to the reader / what to do now.
   - Translate the first important jargon term once, within existing Evidence.
   - Do not place two high-density technical sections back-to-back without a decision bridge.
   - Move nonessential implementation detail after the reader can understand the decision.
   - No fabricated experience, emotion, analogy facts, causality, numbers or guarantees.

2. **Reader-only Production repair**
   - Applies only to fresh Production candidates.
   - Requires Evidence state `SUFFICIENT` and `decision_scope_safe=true`.
   - Every blocker must be in the proven Reader Value accessibility family.
   - Authorizes the canonical article orchestrator's existing one-quality-retry-per-article path; Run341 itself never calls a provider and never loops.

3. **Mixed Fact + Reader retry**
   - Existing HARD/REVIEW retry authority remains unchanged.
   - When Reader Value reasons coexist, the retry instruction explicitly freezes supported Fact/Evidence/Decision semantics while permitting reader-path edits to title punctuation, opening/section ordering, jargon translation, redundancy and nonessential implementation detail.

4. **Fail-closed invariants**
   - Evidence URLs and evidence meaning are not to change during Reader Repair.
   - Decision / Decision Score / Action semantics are not to change.
   - Supported numbers, units, named facts and conditions are not to be strengthened or invented.
   - Fact, Evidence, Publication and Reader gates still rerun after repair; failure remains non-Ready.
   - Existing Pending Retry and Current-policy Ready recovery policies remain authoritative for their own origins.

## Provenance and reconciliation

`run341_production_reader_repair.py` is a Publication Contract policy file. Its bytes therefore change the automatic policy SHA. It is also a Note Ready reconciliation trigger, so historical Ready content cannot silently be treated as current-policy after Run341 changes.

## Cost policy

Run341 introduces no new provider route and no separate model-call budget. It may convert a reader-only `no_retry` outcome into the single quality retry that the existing article lifecycle already permits. Provider and per-run request budgets remain authoritative.
