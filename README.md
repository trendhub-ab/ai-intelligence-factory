# AI Intelligence Factory

## Production baseline

- **Current functional baseline:** Run199 — publish-safe note VM preflight
- **Current repository organization baseline:** Run200 — repository consolidation with no intended runtime behavior change
- **Daily:** PAUSED
- **Production execution:** manual ONE-SHOT / explicitly dispatched operational workflows only
- Canonical specification: `AI_Intelligence_Factory_最終仕様書.md`

New development must start from `main`. Historical/archive branches are reference-only and must not be used as a development base.

## Active runtime map

### Core production pipeline

- `pipeline.py` — acquisition, screening, Deep Dive, article quality, Notion persistence and operational state
- `production_pipeline.py` — stable production entrypoint
- `decision_intelligence.py` — Decision Intelligence persistence/domain logic
- `editorial_eyecatch.py` — deterministic note Editorial Eyecatch renderer
- `evidence_ledger.py`, `evidence_authority.py` — Evidence Ledger / authority / binding logic
- `inventory_bootstrap.py`, `portfolio_inventory_bootstrap.py` — subscriber inventory bootstrap
- `technology_portfolio_policy.py`, `daily_portfolio_review.py` — portfolio prioritization/review logic
- `context_first_enrichment.py` — Context-First Decision Intelligence enrichment
- `subscription_attribution.py` — aggregate/privacy-safe subscription attribution

`production_pipeline.py` currently installs the Run172–Run183 reliability/quality/eyecatch layers, `reader_value_review_bridge`, and `run194_publication_contract` in an explicit order. Those Run-numbered Python modules are **active production code**, not historical clutter, and must not be archived or renamed without a dedicated compatibility refactor and full regression proof.

### note draft automation

The current note path is intentionally layered and fail-closed:

- `note_draft_automation.py` — base private-draft automation
- `run185_note_ready_legacy_skip.py`
- `run186_note_header_image_resilience.py`
- `run187_note_editor_readiness.py`
- `run188_note_header_upload_fallback.py`
- `run189_note_editor_route_gate.py`
- `run190_note_persistent_cloud.py`
- `run191_note_crop_dialog_resilience.py`
- `run193_note_official_header_upload.py`
- `run194_note_current_contract.py`
- `run194_note_persistent_cloud.py`
- `run194_publication_contract.py`
- `run199_note_vm_preflight.py`

`.github/workflows/note-create-draft.yml` first performs a zero-browser, zero-Gemini publication-safety preflight on GitHub-hosted Ubuntu. The GCP Chrome VM starts only when an eligible current-contract article exists, and the selected `sync_id` is pinned into the VM job. Public release remains human-only.

## Repository map

- `tests/` — production regression, adversarial and contract tests
- `.github/workflows/` — Daily, ONE-SHOT, Regression, Inventory, Notion and note operational workflows
- `assets/` — production image/template assets
- `eyecatch_images/` — published Notion-linked Decision Card assets; **not disposable cache**
- `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/` — operational state/history required for production continuity
- `docs/reference/` — architecture/business reference documents
- `docs/archive/` — historical setup, validation, Run notes and cleanup records retained for audit

## Root-document policy

The repository root is reserved for canonical/operator documents and executable entry points. Historical `RUN*.md` implementation notes belong under `docs/archive/`; Git history already preserves their original location and chronology.

The following operator documents are intentionally retained at root for discoverability:

- `AI_Intelligence_Factory_最終仕様書.md`
- `DECISION_INTELLIGENCE_SETUP.md`
- `GEMINI_QUOTA_SETUP.md`
- `NOTION_ACCESS_POLICY.md`
- `REVENUE_PRODUCT_PHASE2_SETUP.md`
- `SUBSCRIPTION_ATTRIBUTION_SETUP.md`

Run200 archived the remaining root-level Run177–Run196 historical notes without changing their file contents. See `docs/archive/repository-cleanup-2026-09-02/REPOSITORY_CLEANUP_MANIFEST_2026-09-02.md`.

## Branch policy

The intended long-lived branches are deliberately small:

- `main` — sole Production baseline and source of truth
- `feature/x-intelligence-layer` — isolated future X Intelligence work
- `integration/main-run147-reconciliation` — retained historical reconciliation snapshot; reference-only

Short-lived feature/fix/ops/Run branches should be removed after their changes are preserved in `main`, merged PRs, tags, or `docs/archive/`. Branch cleanup is administrative and must not be confused with deleting production files from `main`.

## Artifact and state policy

Synthetic/Real Article outputs, Article Audit outputs, temporary regression fixtures, caches, release ZIPs and checksum manifests are generated artifacts and should not be committed as source. GitHub Actions artifacts are the preferred retention location.

Operational state, learning history and published Notion-linked eyecatch assets are intentionally different from disposable artifacts. In particular, do **not** bulk-delete or relocate `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/` or `eyecatch_images/` without an explicit migration plan and reference audit.

Generated output directories are covered by `.gitignore`; if a test or workflow introduces a new generated directory, add it to `.gitignore` before merging.

## Change discipline

Repository cleanup must be behavior-preserving by default:

1. Prove whether a file is referenced by production entrypoints, workflows or tests before moving it.
2. Keep ambiguous files until their dependency status is proven.
3. Move historical documentation to `docs/archive/` rather than deleting it.
4. Preserve operational state and published assets.
5. Run repository-wide falsification and relevant regression checks before merging cleanup into `main`.
