# Run201 Repository Garbage Cleanup

Date: 2026-09-02

## Safety baseline

- Production source of truth before cleanup: `main`
- Starting main SHA: `8cc810dee8859e8d02b0015fb3feed62aad0fd89`
- Cleanup branch: `run201-repository-garbage-cleanup`
- Intent: repository hygiene only; no intended Production runtime behavior change
- Daily remains PAUSED.
- Public note release remains human-only.

## Falsification rules

A file was not treated as garbage merely because it had an old Run number or appeared duplicated. Before removal/retirement we checked whether it was referenced by Production entrypoints, GitHub Actions, tests, operational state, recovery flows, or published Notion-linked assets.

Protected surfaces were explicitly preserved: `.runtime/`, `observed_history/`, `source_roi_history/`, `deferred_deep_dive/`, `eyecatch_images/`, `assets/`, the Run172–Run183 Production runtime overlays, and the Run185–Run199 note safety stack.

## Removed from the active source tree

- `docs/archive/EYECATCH_FINAL_PREVIEW_81.png`
  - Generated validation preview, not a published source asset.
- `inventory_bootstrap_artifacts/README.md`
  - Placeholder existed only to keep a generated artifact directory in Git.
  - `inventory_bootstrap.py` creates the directory at runtime and GitHub Actions uploads it as an artifact.
  - `.gitignore` now ignores the whole directory.

## Retired from active GitHub Actions but preserved byte-for-byte

Moved to `docs/archive/repository-cleanup-2026-09-02/retired-workflows/`:

- `decision-intelligence-migration.yml`
- `japanese-display-label-migration.yml`

Reason: both are completed one-time migration entrypoints. Keeping them runnable in the Actions UI increases accidental schema/write risk. Their Python migration/repair modules remain in source because current tests exercise them and they can still be useful for controlled repair/audit work.

## Moved out of repository root / active operational namespace

- Root `DECISION_INTELLIGENCE_SETUP.md` moved byte-for-byte to:
  `legacy-operator-docs/DECISION_INTELLIGENCE_SETUP_PHASE1_2026-08-21.md`
  - It describes the old Phase 1 migration/setup procedure and already marks parts of the design as superseded by Phase 2.
- `run156_targets.json` and all tracked `external_reviews/*.json` moved byte-for-byte to:
  `external-review-history/`
  - These are historical review inputs/evidence, not current runtime configuration.
  - They remain available for audit/replay by explicit path.
- `run153_backfill_catalog.py` and its dedicated test were moved to `retired-tools/` and `retired-tests/`.
  - The script was a deterministic one-time Run153 catalog generator whose default output recreated the obsolete `external_reviews/run153_backfill.json` path.
  - Its dedicated test validated that retired catalog rather than current Production behavior.

## Corrected stale operational configuration

`.github/workflows/external-review-import.yml` no longer defaults `input_path` to the nonexistent `external_reviews/run153_backfill.json`. The input remains required, so an operator must now deliberately select the review JSON to import.

## Explicit KEEP decisions after falsification

- `member_human_language_ux.py` and `member_human_language_ux_v2.py`: both required; v2 builds on the base implementation.
- `migrate_decision_intelligence.py`: retained because current Decision Intelligence tests import/exercise it and it remains a controlled repair/audit tool.
- `migrate_japanese_display_label.py`: retained because Run120 tests directly exercise its idempotent schema behavior.
- `run164_ai_relevance_calibration.py`: active; `portfolio_inventory_bootstrap.py` imports and installs it.
- `run156_decision_review_import.py`: retained as a stricter zero-provider external-review validation/repair tool; not classified as disposable without a dedicated replacement/equivalence refactor.
- `notion_audit_views.json`: retained as current operator audit configuration.
- `subscription_metrics_template.csv`: retained because the current Subscription Attribution operator guide explicitly instructs operators to copy it.
- `integration-reconciliation-ci.yml`: retained; it is current PR CI and runs repository falsification, full unittest regression, and current-stack Synthetic smoke.
- `daily.yml`: retained intentionally as the hard-disabled PAUSED safety contract.

## Regression contract changes

- Added `tests/test_run201_repository_garbage_cleanup.py` to prevent the removed/retired clutter from returning and to verify protected runtime surfaces remain present.
- Updated the Run200 repository-layout README assertion to recognize Run201 as the repository-organization baseline while retaining all Run200 runtime/safety checks.
- Updated `repository-falsification.yml` so PR/main repository falsification runs both Run200 and Run201 repository-layout contracts.

## Validation status

Local container clone was attempted but the isolated execution environment cannot resolve `github.com`; therefore no local clone-based result is claimed. Formal validation is delegated to GitHub PR checks, especially:

1. Repository-wide Falsification Guard
2. Integration Reconciliation CI / full unittest regression
3. Synthetic smoke through `production_pipeline.py`

Do not merge Run201 into `main` unless required PR checks are green and main remains protected.
