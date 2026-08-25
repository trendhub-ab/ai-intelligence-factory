# AI Intelligence Factory

Production baseline: **Run127 – Intellectual Entertainment Pull**.

## Repository map

- `pipeline.py` — main acquisition, screening, Deep Dive, article quality, Notion pipeline
- `decision_intelligence.py` — Decision Intelligence persistence/domain logic
- `evidence_ledger.py`, `evidence_authority.py` — Evidence Ledger / authority / binding logic
- `inventory_bootstrap.py` — subscriber inventory bootstrap
- `tests/` — production regression and adversarial tests
- `.github/workflows/` — Daily, Regression, Inventory Bootstrap and related workflows
- `assets/` — production image/template assets
- `eyecatch_images/` — published eyecatch assets; do **not** treat as disposable cache
- `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/` — operational state/history used by production continuity
- `docs/reference/` — architecture/business reference documents
- `docs/archive/` — historical validation/setup/mutation documents retained for audit
- `AI_Intelligence_Factory_最終仕様書.md` — canonical specification

## Current Run127 documents

- `RUN127_INTELLECTUAL_ENTERTAINMENT_PULL_SETUP.md`
- `RUN127_INTELLECTUAL_ENTERTAINMENT_PULL_VALIDATION_2026-08-25.md`
- `RUN127_SOURCE_REQUIREMENTS_知的エンタメ強化.md`

## Artifact policy

Synthetic/Real Article outputs, Article Audit outputs, temporary regression fixtures, caches, release ZIPs and checksum manifests are generated artifacts and should not be committed as source. GitHub Actions artifacts are the preferred retention location.

Operational state and published eyecatch assets are intentionally different from disposable artifacts and must not be bulk-deleted without a migration plan.
