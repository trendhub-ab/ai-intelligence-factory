# Run245 — Fact / Source Boundary Validation Modularization

## Purpose

Run245 continues the low-risk `pipeline.py` strangler modularization from the merged Run244 baseline. It mechanically extracts deterministic Fact/Evidence validation helpers while keeping provider, network, persistence and Hard Gate orchestration in `pipeline.py`.

## Production baseline

- Base: Run244 main `d261bc7803cd06a8b61d64efcd8c58ea01bb3ec2`
- Run244 `pipeline.py`: 10,434 lines
- Run245 `pipeline.py`: 9,978 lines
- Physical reduction: 456 lines

This reduction is a maintainability result. It is not evidence that Production E2E runtime became faster; external I/O and model/provider latency remain separate performance concerns.

## Canonical modules

### `fact_validation_signals.py`

Owns the historical deterministic implementations for:

- numeric evidence normalization
- numeric claim condition tagging / compatibility
- protocol-cardinality exception handling
- unsupported numeric claim detection
- sentence-scoped negation and hype detection
- substantive evidence coverage / false-negative claim detection
- unsupported competitor claims
- explicit entity-relation parsing and support checks

### `source_boundary_validation.py`

Owns the historical deterministic implementations for:

- evidence alias expansion
- unsupported named-fact Source Boundary validation

Short all-caps aliases remain token-matched so ordinary strings such as `storage` cannot fabricate `RAG` support.

## Live runtime binding

`pipeline.py` retains thin compatibility wrappers. Before delegation, wrappers bind the current live constants/helpers into the canonical module. This preserves runtime monkeypatch/config behavior instead of freezing mutable pipeline state at import time.

Run245 dedicated tests explicitly falsify rebinding, numeric pattern changes, alias-group changes and Action-risk classifier changes.

## Intentionally retained in `pipeline.py`

Run245 does **not** move:

- Gemini/model invocation
- Gemini quota/budget/pacing/retry logic
- HTTP/network acquisition
- SSRF boundaries
- Product Review source-boundary reconciliation
- Notion reads/writes or destination resolution
- `validate_fact_gate()` or other Hard Gate execution
- Product Review candidate selection/orchestration
- Pending Retry orchestration

## Protected contracts unchanged

Run245 intentionally changes no:

- Gemini model pool or fallback order
- Gemini call-site count
- RPD/RPM/TPM ceilings
- persistent counter or retry budgets
- Deep Dive / Product Review / Pending Retry request budgets
- Fact / Evidence / Decision / Publication / Human Appeal thresholds
- numeric/hype/relation/source-boundary regex semantics
- Screening/Stock eligibility or Decision Score rules
- Notion schema or canonical member destination
- subscriber PII handling
- Daily PAUSED state
- human-only public note release policy

## Fail-closed migration

`run245_fact_validation_migration.py` accepts only the exact Run244 preimage:

- `pipeline.py` line count: 10,434
- SHA256: `9ef54a6e2c0c204e39202babdadfd7bcb486b96f1136b392f7f95b0189af8889`
- exact historical target function sizes
- exact import anchor

Unexpected source shape aborts without rewriting. The postimage is idempotent.

## Initial guarded validation

The guarded bootstrap run completed with:

- migration: 10,434 → 9,978 lines
- compile: PASS
- full pytest: 1,598 passed
- Synthetic smoke: 30/30 passed
- critical failures: 0
- production write isolation: true
- second migration: unchanged / idempotent
- `git diff --check`: PASS

Permanent Run245 module/integration tests and required PR CI are the merge gate; this bootstrap result alone does not authorize merge.
