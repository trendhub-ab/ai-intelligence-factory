# AI Intelligence Factory

## Production baseline

- **Current repository baseline:** Run151 – Conservative Repository Hygiene
- **Latest functional baseline:** Run150 – Dual Eyecatch Architecture
  - free note articles: reader-facing Editorial Eyecatch
  - paid Notion DB: Decision Card with decision metrics
- Canonical specification: `AI_Intelligence_Factory_最終仕様書.md`

New development must start from `main`. Historical/archive branches are reference-only and must not be used as a development base.

## Repository map

- `pipeline.py` — main acquisition, screening, Deep Dive, article quality, Notion pipeline
- `editorial_eyecatch.py` — deterministic note Editorial Eyecatch renderer
- `decision_intelligence.py` — Decision Intelligence persistence/domain logic
- `evidence_ledger.py`, `evidence_authority.py` — Evidence Ledger / authority / binding logic
- `inventory_bootstrap.py`, `portfolio_inventory_bootstrap.py` — subscriber inventory bootstrap
- `technology_portfolio_policy.py`, `daily_portfolio_review.py` — portfolio prioritization/review logic
- `context_first_enrichment.py` — Context-First Decision Intelligence enrichment
- `subscription_attribution.py` — aggregate/privacy-safe subscription attribution
- `tests/` — production regression and adversarial tests
- `.github/workflows/` — Daily, Regression, Inventory Bootstrap and operational workflows
- `assets/` — production image/template assets
- `eyecatch_images/` — published Notion-linked Decision Card assets; **not disposable cache**
- `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/` — operational state/history required for production continuity
- `docs/reference/` — architecture/business reference documents
- `docs/archive/` — historical setup/validation/cleanup documents retained for audit

## Operator setup documents

The following root-level documents are intentionally retained for operator discoverability:

- `DECISION_INTELLIGENCE_SETUP.md`
- `GEMINI_QUOTA_SETUP.md`
- `REVENUE_PRODUCT_PHASE2_SETUP.md`
- `SUBSCRIPTION_ATTRIBUTION_SETUP.md`

Historical Run setup/validation documents have been moved to `docs/archive/` rather than deleted.

## Branch policy

Active/preserved branches are intentionally limited to:

- `main` — sole Production baseline and source of truth
- `feature/x-intelligence-layer` — isolated future X Intelligence work
- `integration/main-run147-reconciliation` — retained historical reconciliation snapshot; reference-only

Merged fix branches, superseded experiment branches and one-shot cleanup branches should be deleted after their relevant history is preserved in `main`, merged PRs or `docs/archive/`.

## Artifact policy

Synthetic/Real Article outputs, Article Audit outputs, generated note eyecatches, temporary regression fixtures, caches, release ZIPs and checksum manifests are generated artifacts and must not be committed as source. GitHub Actions artifacts are the preferred retention location.

Operational state, learning history and published Notion-linked eyecatch assets are intentionally different from disposable artifacts and must not be bulk-deleted without an explicit migration plan.

Generated output directories are covered by `.gitignore`; if a test or workflow introduces a new generated directory, add it to `.gitignore` before merging.
