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

## Run128
- `RUN128_NON_ENGINEER_ACCESSIBILITY_BRIDGE_SETUP.md`
- `RUN128_NON_ENGINEER_ACCESSIBILITY_BRIDGE_VALIDATION_2026-08-25.md`


### Run130 Fresh Article Regression
`Real Article Regression Test` の手動実行時に `article_set` を選択できます。`fixed` は従来の固定A/B比較、`fresh` は新規候補3件による本番耐性確認です。freshの候補選定は0 Gemini Screening call・Notion READ ONLY・Production writeなしです。詳細は `RUN130_FRESH_ARTICLE_REGRESSION_SETUP.md` を参照してください。
