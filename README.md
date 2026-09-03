# AI Intelligence Factory

## Production baseline

- **Current functional baseline:** Run209 — Gemini timeout RPD fail-closed
- **Current documentation governance baseline:** Run210 — Documentation Freshness Guard
- **Current paid member sync baseline:** Run211 — paid member sync ordering
- **Current paid member UX baseline:** Run214 — current-authority action specificity
- **Current repository organization baseline:** Run201 — repository garbage cleanup without intended runtime behavior change
- **Daily:** PAUSED
- **Production execution:** manual ONE-SHOT / explicitly dispatched operational workflows only
- Canonical specification: `AI_Intelligence_Factory_最終仕様書.md`
- Gemini quota specification: `GEMINI_QUOTA_SETUP.md`

New development must start from `main`. Historical/archive branches are reference-only and must not be used as a development base.

## Active runtime map

### Core production pipeline

- `pipeline.py` — acquisition, screening, Deep Dive, article quality, Notion persistence and operational state
- `production_pipeline.py` — stable production entrypoint and runtime-layer installer
- `run203_runtime_state_channel.py` — Production runtime-state continuity / writability preflight
- `gemini_timeout_rpd_fail_closed.py` — Run209 timeout RPD fail-closed accounting; keeps the 18-request Flash safety ceiling
- `gemini_transient_recovery.py` — bounded transient provider recovery / cooldown
- `decision_intelligence.py` — Decision Intelligence persistence/domain logic
- `editorial_eyecatch.py` — deterministic note Editorial Eyecatch renderer
- `evidence_ledger.py`, `evidence_authority.py` — Evidence Ledger / authority / binding logic
- `inventory_bootstrap.py`, `portfolio_inventory_bootstrap.py` — subscriber inventory bootstrap
- `technology_portfolio_policy.py`, `daily_portfolio_review.py` — portfolio prioritization/review logic
- `context_first_enrichment.py` — Context-First Decision Intelligence enrichment
- `subscription_attribution.py` — aggregate/privacy-safe subscription attribution

`production_pipeline.py` currently installs the runtime-state/quota layers, Run172–Run183 reliability/quality/eyecatch layers, `reader_value_review_bridge`, `run208_reader_value_repair`, and `run194_publication_contract` in an explicit order. These Run-numbered Python modules are **active production code**, not historical clutter, and must not be archived or renamed without a dedicated compatibility refactor and full regression proof.

### Pending Retry fast lane

`pending_retry_validation.py` is the bounded low-cost recovery path for high-value Pending Retry articles.

- no fresh collection/screening
- score-ranked recovery
- max 3 dedicated requests in fast-lane mode
- first 503 cools that model for the rest of the fast-lane run
- one Reader Value recompose at most, only for repairable reader-only failures
- stop after first successful article
- no public note release

### Paid member product sync — Run211

Member-facing Notion data is derived in a fixed order rather than by parallel writers:

**source/product update → Subscriber Decision Brief Sync → Member Presentation Sync**

- Daily and ONE-SHOT feed Subscriber Decision Brief first.
- Subscriber Inventory Bootstrap **apply** also feeds Subscriber Decision Brief.
- Inventory **plan** remains read-only and does not fan out into member writes.
- Member Presentation Sync follows Subscriber Decision Brief Sync, rather than racing Daily/ONE-SHOT/Inventory directly.
- Subscriber Decision Brief Sync and Member Presentation Sync share the `member-derived-notion-writes` lock.
- These derived member workflows do not receive `GEMINI_API_KEY`.
- `関連記事` is propagated only when the source already contains a verified URL; no URL is invented before human note publication.

### Paid member reviewed-copy recovery — Run212

`run212_member_review_copy.py` is a presentation-only compatibility layer for the paid member Decision Intelligence product.

- Run201 archived historical external Product Review JSON remains non-authoritative history; it is not restored to the active `external_reviews/` runtime namespace.
- Archived review data may supply only `plain_summary` and `topic_trigger`, and only where the current member copy is a deterministic fallback/generic topic.
- Current non-fallback summaries remain authoritative.
- Historical score, status, judgment reason, risk, best-for, avoid-for, Evidence and primary URL can never override current Decision Intelligence state through the archive path.
- Explicitly time-sensitive archive copy such as dated “時点” claims, “現時点”, “最新”, and freshness/update claims is rejected instead of being mechanically rewritten.
- If a future current `external_reviews/` source exists, active review copy outranks archive copy and keeps the existing Run170 behavior.
- Run212 contains no Gemini/provider path and keeps derived member sync zero-Gemini.

### Paid member topic specificity — Run213

`run213_member_topic_specificity.py` layers on Run212 without weakening its archive-safety boundary.

- Run212 remains responsible for safe archive copy recovery.
- If the final post-Run212 `今回の話題` is still the deterministic generic topic, Run213 may reuse only the **current authoritative `判断理由`** as the topic fallback.
- Missing or malformed current reasons fail safe and leave the existing topic unchanged.
- Existing non-generic topics are never replaced.
- Run170.4 keeps its existing role-separation pass, so a promoted topic does not leave `判断理由` duplicated; the reason is re-derived from current risk/decision context where necessary.
- Known mechanical mixed-language artifacts `Safety 根拠` and `Transfer 根拠` are repaired narrowly in member-visible copy; product names, identifiers, URLs, scores, statuses, Evidence and categories are not rewritten.
- Run213 adds no historical decision authority, no new factual claim, and no Gemini/provider request path.

### Paid member action specificity — Run214

`run214_member_action_specificity.py` layers on Run213 and reduces repetitive `次にやること` copy using only current member-product context.

- Only known deterministic Run170.4 action templates are eligible; explicit/source-specific actions are left untouched.
- The existing action body, test counts, user counts, time windows and comparison metrics are preserved.
- Current `向いている用途` (`best_for`) is the first context source.
- If `向いている用途` is unavailable, only the current non-generic post-Run213 `今回の話題` may provide context.
- Missing usable context fails safe and keeps the previous action unchanged.
- Run214 does not change score, status, Evidence, risk, primary URL, category, Product Review or article-generation state.
- Member Presentation workflow runs the Run214 wrapper for presentation and body entrypoints.
- Run214 contains no Gemini/provider request path and keeps derived member sync zero-Gemini.

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

## Gemini quota safety

The repository-local Persistent Counter is a safety control, not the Google quota API. Google AI Studio Rate Limits remains the Project-wide external source of truth.

- 3.5 / 3.6 / 3.7 Flash stay capped at **18 requests/day** in Production even when AI Studio currently exposes 20 RPD.
- The remaining 2 requests are safety margin, not spare capacity to consume.
- Run209 keeps timeout reservations counted; transport/watchdog timeout does not restore Factory RPD availability.
- `.runtime/` is protected Production continuity state.

See `GEMINI_QUOTA_SETUP.md` for the full contract.

## Repository map

- `tests/` — production regression, adversarial and contract tests
- `.github/workflows/` — currently actionable Daily, ONE-SHOT, Regression, Inventory, Notion and note workflows only
- `assets/` — production image/template assets
- `eyecatch_images/` — published Notion-linked Decision Card assets; **not disposable cache**
- `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/` — operational state/history required for production continuity
- `docs/reference/` — architecture/business reference documents
- `docs/archive/` — historical setup, validation, retired workflows, Run notes and cleanup records retained for audit

## Root-document policy

The repository root is reserved for canonical/operator documents and executable entry points. Historical `RUN*.md` implementation notes and superseded setup documents belong under `docs/archive/`; Git history preserves their original location and chronology.

The following operator documents are intentionally retained at root for discoverability:

- `AI_Intelligence_Factory_最終仕様書.md`
- `GEMINI_QUOTA_SETUP.md`
- `NOTION_ACCESS_POLICY.md`
- `REVENUE_PRODUCT_PHASE2_SETUP.md`
- `SUBSCRIPTION_ATTRIBUTION_SETUP.md`

The old Decision Intelligence Phase 1 migration guide is archived at `docs/archive/repository-cleanup-2026-09-02/legacy-operator-docs/DECISION_INTELLIGENCE_SETUP_PHASE1_2026-08-21.md`. Completed one-time migration workflows are retained under `docs/archive/repository-cleanup-2026-09-02/retired-workflows/` instead of remaining runnable in GitHub Actions.

## Branch policy

The intended long-lived branches are deliberately small:

- `main` — sole Production baseline and source of truth
- `feature/x-intelligence-layer` — isolated future X Intelligence work
- `integration/main-run147-reconciliation` — retained historical reconciliation snapshot; reference-only
- `daily-once-20260901` — retained ONE-SHOT operational history
- `run192-note-failure-snapshot` — retained failure/recovery forensic snapshot
- `run200-pre-archive-safety-snapshot` — retained pre-cleanup safety snapshot

Short-lived feature/fix/ops/Run branches should be removed after their changes are preserved in `main`, merged PRs, tags, or `docs/archive/`. Branch cleanup is administrative and must not be confused with deleting production files from `main`.

## Artifact and state policy

Synthetic/Real Article outputs, Article Audit outputs, temporary regression fixtures, caches, release ZIPs, previews and checksum manifests are generated artifacts and should not be committed as source. GitHub Actions artifacts are the preferred retention location.

Operational state, learning history and published Notion-linked eyecatch assets are intentionally different from disposable artifacts. In particular, do **not** bulk-delete or relocate `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/` or `eyecatch_images/` without an explicit migration plan and reference audit.

Generated output directories are covered by `.gitignore`; if a test or workflow introduces a new generated directory, add it to `.gitignore` before merging.

## Documentation freshness policy

Run210 makes documentation freshness a CI contract rather than a manual reminder. Run211 extends that contract to the paid member data-sync ordering. Run212 adds the archive-copy authority boundary. Run213 adds the current-authority final topic fallback. Run214 adds current-context action specificity without changing the Run209 functional baseline.

- Active runtime layers in `production_pipeline.py` must be represented in the canonical specification.
- README / canonical spec baseline labels must remain aligned.
- Gemini safety ceiling 18, timeout fail-closed behavior, Daily PAUSED, and Pending Retry fast-lane contracts must remain consistent with code/workflows.
- Subscriber Decision Brief Sync must precede Member Presentation Sync; Inventory plan must not trigger downstream member writes.
- Archived Product Review data must remain copy-only when reused by Run212 and must not become authoritative for current decision state.
- Run213 topic fallback may use current `判断理由` only after Run212 leaves a deterministic generic topic; it must not source historical judgment fields or generate new facts.
- Run214 action specificity may contextualize known deterministic templates only from current `向いている用途`, then current non-generic `今回の話題`; it must not rewrite explicit actions, test conditions or Decision/Evidence state.
- A Production behavior change that makes canonical documentation stale must fail CI until the documentation is updated in the same change set.

## Change discipline

Repository cleanup must be behavior-preserving by default:

1. Prove whether a file is referenced by production entrypoints, workflows or tests before moving it.
2. Keep ambiguous files until their dependency status is proven.
3. Move historical documentation and retired operational definitions to `docs/archive/` rather than deleting audit history.
4. Preserve operational state and published assets.
5. Run repository-wide falsification, Documentation Freshness Guard, and relevant regression checks before merging into `main`.
