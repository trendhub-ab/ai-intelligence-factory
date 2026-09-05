# Run241 — Batched Pipeline Modularization

## Purpose

Run241 changes the slimming cadence from one small extraction per Run to a guarded batched extraction. Five deterministic domains were moved together so one PR, one full pytest run and one Synthetic smoke can validate the whole batch.

## Physical result

- Run240 `pipeline.py`: **12,461 lines**
- Run241 `pipeline.py`: **11,497 lines**
- Net reduction: **964 lines**

The target remains a thin orchestration/compatibility surface rather than business logic duplication.

## Canonical domains extracted

### `candidate_identity.py`
Conservative URL canonicalization and cross-source candidate identity URL collection. Tracking parameters and presentation-only differences may be removed; meaningful path/query identity is preserved.

### `note_manuscript.py`
Deterministic note manuscript shaping: Markdown normalization, Reader-First summary/header shaping, source/evidence presentation, subscription attribution/tracking URL formatting and CTA assembly. Runtime subscription flags/URLs/campaign IDs remain live-bound by `pipeline.py`.

### `gate_reasoning.py`
Stable gate reason-code, severity, disposition and audit-record shaping. This module **does not execute** Fact, Evidence, Publication or Human Appeal gates; it classifies already-produced gate outcomes.

### `screening_protocol.py`
Deterministic screening metadata protocol: round-robin ordering, commercial/shelf/topic helpers, prompt construction and JSON parsing/salvage. It contains no Gemini/provider invocation. Live thresholds and portfolio configuration remain pipeline-bound.

### `source_roi_policy.py`
Zero-model Source ROI smoothing, profile, allocation and run-metric shaping. Provider/quota failures remain excluded from the attempt denominator exactly as before. Live learning thresholds and source limits remain pipeline-bound.

## Protected contracts unchanged

Run241 changes ownership, not policy.

- No Gemini model, fallback or call-site change.
- No RPD/RPM/TPM, Persistent Counter, pacing, retry budget or Pending Retry change.
- No Fact / Evidence / Decision / Publication / Human Appeal threshold or blocking-semantics change.
- No Screening score threshold, Stock eligibility, Deep Dive request budget or Decision Score formula change.
- No Notion schema, canonical member destination or subscriber-product change.
- Daily remains **PAUSED**.
- Public note release remains **human-only**.
- Regression remains Production-write isolated.

## Live-binding strategy

`pipeline.py` keeps thin wrappers where runtime monkeypatch/config compatibility matters. Dynamic values are passed at call time, including subscription attribution settings, portfolio topics, Screening thresholds, Source ROI learning configuration and article helpers. Canonical modules do not freeze those Production values during import.

## Migration safety

`run241_batched_modularization_migration.py` is the fail-closed audit migration utility.

It requires the exact Run240 preimage, validates anchor functions, performs AST-bounded replacements, parses the postimage and asserts the exact 11,497-line ownership result. Unexpected source shape stops without writing.

## Dedicated falsification

- `tests/test_run241_batched_modules.py`: 15 module/contract tests
- `tests/test_run241_batched_integration.py`: 7 live-binding/ownership tests
- Dedicated total: **22 tests**

The initial migration bootstrap safely stopped before writing when its expected postimage line count differed by two lines. The target was reconciled to the exact GitHub preimage/postimage result; Production logic was not weakened. A separate workflow-token limitation prevented a GitHub Action from updating another workflow file, so workflow changes were applied through the repository connector instead of broadening permissions.

## CI contract

Run241 is wired permanently into:

- Repository-wide Falsification Guard
- Integration Reconciliation CI
- existing Cross DB and Notion Access guards through the PR

Temporary write-enabled bootstrap utilities/workflows are not part of the Production candidate and must be removed before PR review.
