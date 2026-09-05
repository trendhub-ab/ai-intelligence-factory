# Run246 Repository Garbage Cleanup — 2026-09-05

## Purpose

Remove verified repository clutter without changing Production behavior. Nothing is classified as garbage merely because it has an old Run number. Active runtime layers, policy overlays, operational state, publication assets, audit migrations, and current operator entry points remain protected.

## Retired from active/root surfaces

1. `.github/workflows/run130-portfolio-test.yml`
   - Historical path-specific portfolio CI.
   - Current `integration-reconciliation-ci.yml` already runs Run131 profit portfolio, Run132 context-first, inventory bootstrap, full pytest, and Synthetic smoke.
   - Retired copy preserved under `retired-workflows/`.

2. `migrate_decision_intelligence.py`
   - One-time legacy Internal DB migration tool.
   - Its active migration workflow had already been retired in the 2026-09-02 cleanup.
   - No current import/reference was found before retirement.
   - Exact blob preserved under `retired-tools/`.

3. `migrate_japanese_display_label.py`
   - One-time schema migration tool.
   - Its active migration workflow had already been retired in the 2026-09-02 cleanup.
   - No current import/reference was found before retirement.
   - Exact blob preserved under `retired-tools/`.

## Explicitly retained after falsification

- `run156_decision_review_import.py`: still imported by active decision-density regression tests.
- `run164_ai_relevance_calibration.py`: still installed and verified by active AI relevance calibration tests.
- `portfolio_inventory_bootstrap.py`: current `inventory-bootstrap.yml` Production/operator entry point.
- `regression.yml` and `regression-test.yml`: distinct Synthetic and Real Article regression purposes.
- Run235–Run245 modularization migration utilities: permanent audit/fail-closed migration assets wired into CI.
- `.runtime/`, `observed_history/`, `source_roi_history/`, `deferred_deep_dive/`, `eyecatch_images/`, `assets/`: protected operational state/assets.

## Safety invariants

- No Gemini model/call/quota behavior changed.
- No Fact/Evidence/Decision/Publication/Human Appeal gate changed.
- No Notion schema or destination changed.
- Daily remains PAUSED.
- Public note publication remains human-only.
- No Production write path was added.

## Regression contract

`tests/test_run246_repository_hygiene.py` prevents the retired surfaces from returning to active/root paths and protects the retained runtime/operator/state assets from future over-aggressive cleanup.
