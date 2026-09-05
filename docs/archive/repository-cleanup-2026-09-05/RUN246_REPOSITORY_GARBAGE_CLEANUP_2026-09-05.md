# Run246 Repository Garbage Cleanup — 2026-09-05

## Purpose

Remove verified repository clutter without changing Production behavior. Nothing is classified as garbage merely because it has an old Run number. Active runtime layers, policy overlays, operational state, publication assets, audit migrations, and current operator entry points remain protected.

## Retired from active surfaces

### `.github/workflows/run130-portfolio-test.yml`

- Historical path-specific portfolio CI.
- Current `integration-reconciliation-ci.yml` already runs Run131 profit portfolio, Run132 context-first, Inventory Bootstrap regression, full pytest, and Synthetic smoke.
- Removing this workflow does not remove those checks; it removes a redundant duplicate CI surface.
- Exact historical copy is preserved under `retired-workflows/`.

## Candidates rejected by falsification

### `migrate_decision_intelligence.py`

Initially looked like a completed one-time migration tool because its dispatch workflow had already been retired. Full pytest disproved the garbage hypothesis: `tests/test_decision_intelligence.py` directly imports the module to preserve migration/entity-resolution safety. The root module was therefore restored unchanged and is explicitly protected by Run246.

### `migrate_japanese_display_label.py`

Initially looked like a completed one-time schema tool because its dispatch workflow had already been retired. Full pytest disproved the garbage hypothesis: `tests/test_run120_japanese_display_label.py` directly imports the module to verify migration behavior. The root module was therefore restored unchanged and is explicitly protected by Run246.

## Other explicitly retained surfaces

- `run156_decision_review_import.py`: still imported by active decision-density regression tests.
- `run164_ai_relevance_calibration.py`: still installed and verified by active AI relevance calibration tests.
- `portfolio_inventory_bootstrap.py`: current `inventory-bootstrap.yml` Production/operator entry point.
- `regression.yml` and `regression-test.yml`: distinct Synthetic and Real Article regression purposes.
- Run235–Run245 modularization migration utilities: permanent audit/fail-closed migration assets wired into CI.
- `backfill_evidence_ledger.py`: current `evidence-ledger-maintenance.yml` operator entry point.
- `.runtime/`, `observed_history/`, `source_roi_history/`, `deferred_deep_dive/`, `eyecatch_images/`, `assets/`: protected operational state/assets.

## Safety invariants

- No Gemini model/call/quota behavior changed.
- No Fact/Evidence/Decision/Publication/Human Appeal gate changed.
- No Notion schema or destination changed.
- Daily remains PAUSED.
- Public note publication remains human-only.
- No Production write path was added.

## Regression contract

`tests/test_run246_repository_hygiene.py` prevents the retired workflow from returning to the active workflow set, proves its regression coverage remains in Integration CI, and protects candidates that full-regression falsification showed are still required.
