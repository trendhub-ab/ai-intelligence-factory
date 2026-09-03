# AI Intelligence Factory

## Production baseline

- **Current functional baseline:** Run209 — Gemini timeout RPD fail-closed
- **Current documentation governance baseline:** Run210 — Documentation Freshness Guard
- **Current paid member sync baseline:** Run211 — paid member sync ordering
- **Current paid member UX baseline:** Run215 — final current-authority action dedup
- **Current paid member commerce/onboarding baseline:** Run217 — zero-API monetization readiness / product fulfillment
- **Current paid member navigation/UI baseline:** Run218 — PC-first member UX reconciliation
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
- Run214 contains no Gemini/provider request path and keeps derived member sync zero-Gemini.

### Paid member final action dedup — Run215

`run215_member_action_final_dedup.py` is a narrow presentation-only refinement on top of Run214.

- Specific current `向いている用途` still has highest priority.
- Two known deterministic broad `向いている用途` fallbacks are treated as generic context, not product-specific context.
- When such generic `向いている用途` coexists with a current non-generic post-Run213 `今回の話題`, Run215 uses the current topic to contextualize the existing safe action template.
- If no specific current topic exists, Run215 preserves Run214 behavior rather than deleting context or inventing a new action.
- Explicit/source-specific actions remain untouched and the Run214 action body, test counts, user counts, time windows and metrics remain unchanged.
- Run215 does not change score, status, Evidence, risk, primary URL, category, Product Review or article-generation state.
- Member Presentation workflow runs the Run215 wrapper for presentation and body entrypoints.
- Run215 contains no Gemini/provider request path and keeps derived member sync zero-Gemini.

### Paid member commerce / onboarding — Run217

Run217 established zero-model product readiness, current inventory/Digest fulfillment, and the legacy-database quarantine. Its original member-home navigation conclusion was corrected by Run218.

- Current member presentation DB: `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1`
- Current member presentation data source: `d1461b6f-0940-4bf9-803a-6686a37c4ba2`
- The older 100-row duplicate data source `ec2ac2b3-89b6-4242-89b9-e94060826fca` is explicitly `旧版・使用禁止`; it remains audit history and must not be used for onboarding.
- `会員限定Digest｜2026年9月 初回版` was built from current authoritative DB content with zero model calls and remains part of the paid-product fulfillment contract.
- The page created in Run217 (`3d0479ff-dca9-819e-9da0-c951225de6b3`) is now `【旧・統合済み】AI Intelligence｜会員ホーム` and is **not** the canonical onboarding destination.
- Full historical/correction record: `docs/reference/RUN217_ZERO_API_MONETIZATION_READINESS.md`.

### Paid member navigation / UI — Run218

Run218 is the current customer-facing navigation/UI contract.

- Canonical member home: `AI Decision Intelligence｜会員ホーム`
- Canonical Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- Canonical URL: `https://app.notion.com/p/3c5479ffdca98103bff0f2d5f408d35f`
- **PC-first:** PC is the primary experience; mobile/simple views are secondary fallback surfaces only.
- The first home surface is a **live Top3** linked view driven by `注目順位 <= 3`; manual fixed product cards are not the authority.
- High-priority practical candidates are deliberately separated from the full inventory so a shortlist does not degrade into a 100+ row dump.
- `全件検索｜PC`, judgment/category views, the PC judgment board, rising-items view, and Deep Tech view use member-relevant fields rather than internal identifiers.
- The former blank `今月の重要変化` primary surface is reconciled without changing source semantics: the PC home shows recent authoritative changes with `評価の変化 >= 20` or `<= -20`, while `今月の重要変化` itself is not rewritten merely to populate a view.
- A primary member surface must not present an unexplained blank table when an already-authoritative presentation fallback exists; otherwise it must show an explicit empty-state explanation.
- The current presentation DB and Digest are children of the canonical home, so normal customer breadcrumbs no longer pass through the internal `mlflow/mlflow` source record.
- Full current contract: `docs/reference/RUN218_MEMBER_UX_RECONCILIATION.md`.

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

Run210 makes documentation freshness a CI contract rather than a manual reminder. Run211 extends that contract to the paid member data-sync ordering. Run212 adds the archive-copy authority boundary. Run213 adds the current-authority final topic fallback. Run214 adds current-context action specificity. Run215 removes only the residual deterministic action duplicates caused by generic `向いている用途`, without changing the Run209 functional baseline. Run217 adds the paid-product fulfillment/commerce baseline. Run218 corrects the actual customer-facing member navigation and establishes the PC-first UI contract without changing the Run209 functional baseline.

- Active runtime layers in `production_pipeline.py` must be represented in the canonical specification.
- README / canonical spec baseline labels must remain aligned.
- Gemini safety ceiling 18, timeout fail-closed behavior, Daily PAUSED, and Pending Retry fast-lane contracts must remain consistent with code/workflows.
- Subscriber Decision Brief Sync must precede Member Presentation Sync; Inventory plan must not trigger downstream member writes.
- Archived Product Review data must remain copy-only when reused by Run212 and must not become authoritative for current decision state.
- Run213 topic fallback may use current `判断理由` only after Run212 leaves a deterministic generic topic; it must not source historical judgment fields or generate new facts.
- Run214 action specificity may contextualize known deterministic templates only from current product fields and must not rewrite explicit actions, test conditions or Decision/Evidence state.
- Run215 may bypass only known generic `向いている用途` fallbacks when a current specific topic exists; it must preserve specific best-for context and must not invent uniqueness for its own sake.
- Run217 legacy DB quarantine and Digest fulfillment remain valid, but its parallel home page is superseded.
- Run218 onboarding must point paid members to `AI Decision Intelligence｜会員ホーム` (`3c5479ff-dca9-8103-bff0-f2d5f408d35f`), keep PC-first/mobile-secondary navigation, and must not regress to the superseded Run217 home or legacy 100-row DB.
- Run218 must not rewrite `今月の重要変化` merely to avoid a blank view; presentation fallback and source semantics stay separate.
- A Production behavior change that makes canonical documentation stale must fail CI until the documentation is updated in the same change set.

## Change discipline

Repository cleanup must be behavior-preserving by default:

1. Prove whether a file is referenced by production entrypoints, workflows or tests before moving it.
2. Keep ambiguous files until their dependency status is proven.
3. Move historical documentation and retired operational definitions to `docs/archive/` rather than deleting audit history.
4. Preserve operational state and published assets.
5. Run repository-wide falsification, Documentation Freshness Guard, and relevant regression checks before merging into `main`.
