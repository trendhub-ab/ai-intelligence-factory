# AI Intelligence Factory

## Production baseline

- **Current functional baseline:** Run209 — Gemini timeout RPD fail-closed
- **Current documentation governance baseline:** Run210 — Documentation Freshness Guard
- **Current paid member sync baseline:** Run211 — paid member sync ordering
- **Current paid member UX baseline:** Run215 — final current-authority action dedup
- **Current paid member commerce/onboarding baseline:** Run217 — zero-API monetization readiness / product fulfillment
- **Current paid member navigation/UI baseline:** Run218 — PC-first member UX reconciliation
- **Current paid member human-language UI baseline:** Run219 — non-engineer member presentation language
- **Current paid member DB destination baseline:** Run220 — canonical member DB cutover / fail-closed destination
- **Current paid member DB hosting baseline:** Run221 — API-host isolation / member-view separation
- **Current stock lifecycle baseline:** Run225 — zero-model Fresh/Aging/Evergreen/Archive active-stock management
- **Current free article editorial planning baseline:** Run226 — evidence-bounded human editorial planning / reader delight without template quotas
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
- `run225_stock_lifecycle.py`, `stock_lifecycle_reconcile.py` — zero-model Screening Stock freshness lifecycle / source reconciliation
- `run225_portfolio_lifecycle.py`, `run225_member_lifecycle_ui.py` — Archive exclusion from active review/member-home ranking without deletion
- `run226_reader_delight_planning.py` — Evidence-bounded pre-draft Reader Tension / Discovery / Consequence / Explanation Bridge / Editorial Point of View planning using the existing article-generation request; no style-count Hard Gate and no new model call
- `context_first_enrichment.py` — Context-First Decision Intelligence enrichment
- `subscription_attribution.py` — aggregate/privacy-safe subscription attribution

`production_pipeline.py` installs the active runtime-state/quota, reliability/quality/eyecatch, Reader Value and publication-contract layers in explicit order. Run-numbered Python modules referenced by current entrypoints are active Production code and must not be archived or renamed without compatibility proof and full regression.

### Pending Retry fast lane

`pending_retry_validation.py` remains the bounded low-cost recovery path for high-value Pending Retry articles.

- no fresh collection/screening
- score-ranked recovery
- max 3 dedicated requests in fast-lane mode
- first 503 cools that model for the rest of the fast-lane run
- one Reader Value recompose at most, only for repairable reader-only failures
- stop after first successful article
- no public note release

## Paid member product contracts

### Run211 — derived product sync ordering

Member-facing Notion data is derived in a fixed order:

**source/product update → Subscriber Decision Brief Sync → Member Presentation Sync**

- Daily and ONE-SHOT feed Subscriber Decision Brief first.
- Subscriber Inventory Bootstrap **apply** also feeds Subscriber Decision Brief.
- Inventory **plan** remains read-only and does not fan out into member writes.
- Member Presentation Sync follows Subscriber Decision Brief Sync rather than racing source workflows.
- Subscriber Decision Brief Sync and Member Presentation Sync share `member-derived-notion-writes`.
- These derived workflows do not receive `GEMINI_API_KEY`.
- `関連記事` is propagated only when the source already contains a verified URL.

### Run212 — reviewed-copy recovery

`run212_member_review_copy.py` reuses archived review material as **copy only**, never as current Decision authority.

- allowed archive fields: `plain_summary`, `topic_trigger`
- historical score/status/reason/risk/best-for/avoid-for/Evidence/URL never override current state
- time-sensitive stale archive copy is rejected
- future active review copy outranks archive copy
- zero Gemini/provider path

### Run213 — topic specificity

`run213_member_topic_specificity.py` may replace only a remaining deterministic generic `今回の話題` using the **current** `判断理由`.

- non-generic current topics stay unchanged
- missing/malformed current reasons fail safe
- Run170.4 keeps reason/topic role separation
- known `Safety 根拠` / `Transfer 根拠` artifacts are repaired narrowly
- no historical judgment authority and no Gemini/provider path

### Run214 — action specificity

`run214_member_action_specificity.py` contextualizes only known deterministic `次にやること` templates using current product context.

- existing action body, counts, periods and metrics are preserved
- current `向いている用途` is preferred; current non-generic topic is fallback
- explicit/source-specific actions are not overwritten
- Decision/Evidence state is unchanged
- zero Gemini/provider path

### Run215 — final action dedup

`run215_member_action_final_dedup.py` bypasses only known generic `向いている用途` fallbacks when a current specific topic exists.

- specific best-for context remains highest priority
- explicit actions remain untouched
- uniqueness is not invented for its own sake
- Decision/Evidence state is unchanged
- zero Gemini/provider path

### Run217 — commerce / onboarding history

Run217 established zero-model product readiness, Digest fulfillment and legacy-database quarantine. Its navigation conclusion was corrected by Run218 and its presentation-DB destination was superseded by Run220.

- `会員限定Digest｜2026年9月 初回版` remains the first current-DB Digest built with zero model calls.
- Run217-created page `3d0479ff-dca9-819e-9da0-c951225de6b3` is `【旧・統合済み】AI Intelligence｜会員ホーム` and is not an onboarding destination.
- Older 100-row data source `ec2ac2b3-89b6-4242-89b9-e94060826fca` is `旧版・使用禁止` and audit-only.
- Full history: `docs/reference/RUN217_ZERO_API_MONETIZATION_READINESS.md`.

### Run218 — member navigation / UI

Run218 is the current customer-facing information-architecture contract.

- Canonical member home: `AI Decision Intelligence｜会員ホーム`
- Canonical Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- Canonical URL: `https://app.notion.com/p/3c5479ffdca98103bff0f2d5f408d35f`
- **PC-first:** PC is primary; mobile/simple views are secondary fallback surfaces.
- The first surface is a **live Top3** driven by `注目順位 <= 3`; fixed product cards are not authority.
- High-priority practical candidates stay a shortlist rather than a 100+ row dump.
- Major-change presentation can use authoritative history where `評価の変化 >= 20` or `<= -20` without rewriting `今月の重要変化`.
- A primary member surface must not show an unexplained blank table.
- Physical DB hosting is not part of Run218 navigation authority; Run221 governs that boundary.
- Full contract: `docs/reference/RUN218_MEMBER_UX_RECONCILIATION.md`.

### Run219 — non-engineer human-language UI

`run219_member_human_language_ui.py` is the current member-visible body language layer.

It keeps underlying DB properties and Decision values unchanged while showing plain Japanese such as:

- `このAI・技術をどう見る？`
- `いま、どうする？`
- `そう判断した理由`
- `気をつけたいこと`
- `こんな使い方に向いています`
- `こんな使い方には向きません`
- `確認に使った公式・一次情報`

The body summary hides ADOPT/TEST/WATCH/AVOID codes and presents the Japanese action meaning. Cached/no-op pages must not make unnecessary Notion writes. Run219 contains no Gemini/provider path.

### Run220 — canonical member DB cutover

Run220 fixes the split-brain state discovered after Run219 production verification: the workflow had written Run219 content to an API-visible new DB while the member home still pointed to the former DB.

Current canonical member product destination:

- Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`

Pre-Run220 presentation database is audit-only:

- Database ID: `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1`
- Data Source ID: `d1461b6f-0940-4bf9-803a-6686a37c4ba2`
- Title: `⚠️ 旧版・使用禁止｜AI・技術一覧（Run219前）`

Production invariant:

- `.github/workflows/member-presentation-sync.yml` pins the canonical IDs above.
- `provision_member_presentation_db.py` verifies those exact IDs and **fails closed** if they are unreadable or mismatched.
- Normal Production does not search by title for a fallback destination and does not auto-create another member DB.
- `MEMBER_PRESENTATION_ALLOW_CREATE=false` in the Production workflow.
- Member home views point to the canonical Run220 DB.
- Run219 human-language presentation remains unchanged.
- Gemini/model requests: **0**.

Full destination contract: `docs/reference/RUN220_MEMBER_DB_CANONICAL_CUTOVER.md`.

### Run221 — API-host isolation / member-view separation

Run221 protects the Notion permission boundary discovered during Run220 post-merge validation.

- Customer-facing member home remains `AI Decision Intelligence｜会員ホーム` (`3c5479ff-dca9-8103-bff0-f2d5f408d35f`).
- Canonical product data remains DB `b2787ee0-5b58-4ca7-b4eb-774f60237f1f` / Data Source `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`.
- Physical API host is Page ID `3c5479ff-dca9-8178-867c-d9249a3ff5c8`.
- The physical host is an implementation/access boundary, **not** a member onboarding destination.
- Member navigation exposes the canonical data through member-facing views/links.
- Moving the physical DB under the member home without first granting the GitHub Actions Notion integration access was observed to make canonical resolution return HTTP 404.
- `provision_member_presentation_db.py` therefore verifies both the exact Run220 IDs and the Run221 physical host before writes.
- Production pins `MEMBER_PRESENTATION_API_HOST_PAGE_ID=3c5479ff-dca9-8178-867c-d9249a3ff5c8` and keeps auto-create disabled.
- Do not physically relocate the canonical DB merely for cosmetic breadcrumbs while that move would break automated synchronization.

Full hosting contract: `docs/reference/RUN221_MEMBER_DB_HOST_ISOLATION.md`.

## note private-draft automation

The current note path is intentionally layered and fail-closed:

- `note_draft_automation.py`
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

`.github/workflows/note-create-draft.yml` performs a zero-browser, zero-Gemini publication-safety preflight before any GCP Chrome VM use. Public release remains human-only.

## Gemini quota safety

The repository-local Persistent Counter is a safety control, not the Google quota API. Google AI Studio Rate Limits remains the Project-wide external source of truth.

- 3.5 / 3.6 / 3.7 Flash stay capped at **18 requests/day** in Production even when AI Studio exposes 20 RPD.
- The remaining 2 requests are safety margin, not spare capacity.
- Run209 keeps timeout reservations counted; transport/watchdog timeout does not restore Factory RPD availability.
- `.runtime/` is protected Production continuity state.

See `GEMINI_QUOTA_SETUP.md` for the full contract.

## Repository map

- `tests/` — production regression, adversarial and contract tests
- `.github/workflows/` — actionable Daily, ONE-SHOT, Regression, Inventory, Notion and note workflows
- `assets/` — production image/template assets
- `eyecatch_images/` — published Notion-linked Decision Card assets; **not disposable cache**
- `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/` — protected operational state/history
- `docs/reference/` — current architecture/business/operator references
- `docs/archive/` — historical setup, validation and retired records

## Root-document policy

The repository root is reserved for canonical/operator documents and executable entry points. Historical Run implementation notes and superseded setup documents belong under `docs/archive/`.

Root operator documents intentionally retained for discoverability include:

- `AI_Intelligence_Factory_最終仕様書.md`
- `GEMINI_QUOTA_SETUP.md`
- `NOTION_ACCESS_POLICY.md`
- `REVENUE_PRODUCT_PHASE2_SETUP.md`
- `SUBSCRIPTION_ATTRIBUTION_SETUP.md`

## Branch policy

- `main` is the sole Production baseline and source of truth.
- Historical/reconciliation/safety-snapshot branches are reference-only.
- Short-lived feature/fix/ops/Run branches should be removed after preservation in `main`, merged PRs, tags or `docs/archive/`.

## Artifact and state policy

Synthetic/Real Article outputs, Article Audit outputs, temporary regression fixtures, caches, release ZIPs, previews and checksum manifests are generated artifacts and should not be committed as source.

Operational state and published assets are different. Do **not** bulk-delete or relocate `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/` or `eyecatch_images/` without an explicit migration plan and reference audit.

## Documentation freshness policy

Run210 makes documentation freshness a CI contract. Later member-product Runs extend that contract rather than replacing it.

- Active runtime layers in `production_pipeline.py` must be represented in the canonical specification.
- README / canonical spec baseline labels must remain aligned.
- Gemini safety ceiling 18, timeout fail-closed behavior, Daily PAUSED, and Pending Retry fast-lane contracts must remain consistent with code/workflows.
- Subscriber Decision Brief Sync must precede Member Presentation Sync; Inventory plan must not trigger downstream member writes.
- Run212 archive Product Review reuse remains copy-only.
- Run213 topic fallback remains current-`判断理由`-only.
- Run214 action specificity remains current-context-only.
- Run215 may bypass only known generic best-for fallbacks when a current specific topic exists.
- Run217 legacy DB quarantine and Digest fulfillment remain valid.
- Run218 onboarding must point to `AI Decision Intelligence｜会員ホーム` (`3c5479ff-dca9-8103-bff0-f2d5f408d35f`) and preserve PC-first/mobile-secondary, live Top3 and source/presentation separation for important changes.
- Run219 member-visible bodies must use non-engineer human-language labels and must not expose status codes in the body summary.
- Run220 current Presentation DB must be exactly `b2787ee0-5b58-4ca7-b4eb-774f60237f1f` / `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`; the pre-cutover DB is `旧版・使用禁止`.
- Run221 physical API host must be exactly `3c5479ff-dca9-8178-867c-d9249a3ff5c8`; member home and physical API host are deliberately different surfaces.
- Normal Member Presentation Production must not auto-create, silently choose a different same-title DB, or accept a physical-host mismatch.
- Run226 free-article planning must remain SOURCE BOUNDARY-bounded and must not turn hook/analogy/question/paragraph/list counts into a new human-looking template or new Hard Gate.
- A Production behavior change that makes canonical documentation stale must fail CI until documentation is updated in the same change set.

## change discipline

Repository cleanup must be behavior-preserving by default:

1. Prove whether a file is referenced by production entrypoints, workflows or tests before moving it.
2. Keep ambiguous files until dependency status is proven.
3. Move historical documentation and retired operational definitions to `docs/archive/` rather than deleting audit history.
4. Preserve operational state and published assets.
5. Run repository-wide falsification, Documentation Freshness Guard, and relevant regression checks before merging into `main`.
