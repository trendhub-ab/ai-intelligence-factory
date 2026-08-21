# AI Intelligence Factory Release Validation

Release: Decision Intelligence Phase 1 Shadow Write / Article Quality Gate Calibration 2026-08-21

## Final validation

Notion Token isolation: `NOTION_API_KEY` remains exclusive to the existing Internal DB path; `NOTION_DECISION_INTELLIGENCE_API_KEY` is required for Technology / History product DB operations. Migration reads legacy rows with the former and writes product DB rows with the latter. No implicit fallback is allowed.


- Python syntax: PASS
- Safety Unit: 76/76 PASS
- Notion Persistence: 48/48 PASS
- Adversarial / Failure Injection: 127/127 PASS
- Subscription Attribution: 11/11 PASS
- Decision Intelligence: 33/33 PASS
- unittest discovery: 295/295 PASS
- Synthetic Regression Full: 500/500 PASS
- Critical failures: 0
- Workflow YAML parse: 5/5 PASS
- SHA256SUMS verification: PASS

## Profit optimization additions

- Screening/Calibration output Commercial Value Score and Shelf-Life Score in the same Gemini calls; no extra model requests are added.
- Decision Score remains the only Stock quality threshold. Commercial Value cannot promote Decision Score < 60.
- Deep Dive Priority defaults to 0.65 × Final Decision Score + 0.35 × Commercial Value Score.
- Shelf-Life is classified deterministically as FLASH / TREND / EVERGREEN.
- If TOP3 has no EVERGREEN, one EVERGREEN may enter only when within 8 priority points of the current cutoff.
- Content Portfolio Balance classifies Topic in the same Screening/Calibration calls; no extra model requests are added.
- TOP3 targets at least 2 distinct known Topics only when a new Topic is within 6 priority points of the cutoff. Weak candidates are never forced upward, and OTHER/unknown topic metadata never triggers reordering.
- The sole conditional EVERGREEN slot is protected from Topic rebalancing.
- Notion schema is unchanged. Profit/Portfolio metadata is persisted to Observed history and runtime candidate records.
- Profit scoring can be disabled with ENABLE_PROFIT_PRIORITY=false; Topic balancing can be independently disabled with ENABLE_PORTFOLIO_BALANCE=false.

## Business invariant

Profit/Portfolio optimization may change which eligible Stock candidate is attempted first, but it must never weaken Evidence, Fact, Editorial, Publication Readiness, Human Appeal, Notion persistence, or Stock eligibility rules.

## Source ROI equality correction

- GitHub / Hacker News / arXiv / Product Hunt are coequal mandatory Sources.
- Product Hunt no longer has a lower Source ROI cap than the other three Sources.
- All four Sources use the same `SOURCE_ROI_MAX_FETCH_PER_SOURCE=75`, the same floor, ROI weights, maturity rules, recency decay and exploration logic.
- Equal ROI produces symmetric 50/50/50/50 allocation under the 200-candidate global cap.
- Product Hunt token/freshness handling remains only as an API adapter requirement and does not add Source priority.
- No additional Gemini calls and no Notion schema changes are introduced by this correction.

## Free Article -> Subscription Attribution additions

- Free note remains the acquisition channel; the paid offer remains Decision DB + Monthly Summary. No paid-note article logic was added.
- Stable article_id is based on canonical primary URL, not discovery Source.
- Ready articles receive a tracked subscription CTA only when a valid `SUBSCRIPTION_LANDING_URL` is configured.
- Ready-only attribution manifests contain aggregate article metadata and no subscriber PII.
- Aggregate CSV imports require an explicit attribution method and reject claims beyond the measurement method.
- Unknown article IDs and PII-like columns fail closed.
- Revenue/subscriber metrics are intentionally NOT fed back into ranking in this release.
- No extra Gemini calls and no Notion schema changes.

## Gemini quota protection correction

- Persistent Gemini usage is now scoped by a stable repository-local counter identity, not API-key hash. API-key rotation therefore cannot reset this repository's internal safety counter.
- Legacy same-day `key_scopes` / `project_scopes` are conservatively merged into the new repository-local counter scope. Raw repository name, Project ID and API keys are never persisted in the counter file.
- Production and Real Article Regression no longer fail only because `GEMINI_QUOTA_PROJECT_ID` is missing. They fall back to the stable GitHub repository scope; only the absence of any stable counter scope fails closed.
- `GeminiUsageAudit` records each attempted request by model, purpose, short candidate/batch context, success/error outcome, and returned token usage without storing prompts or unpublished article bodies.
- Usage audit JSON is written under `gate_history/` for private artifact retention; Daily Telegram output includes compact model/purpose attempt counts.
- Existing per-model safety caps remain conservative (`18` for 20-RPD Flash models; `450` for 500-RPD Flash-Lite models in the current workflow configuration).
- The repository-local counter is deliberately not described as authoritative Project-wide usage. Manual AI Studio / other-repository usage must be checked in the AI Studio Rate Limits dashboard.

## Gemini quota efficiency corrections

- Deep Dive local request budget is consumed only after Persistent Counter reservation succeeds. A model rejected at its repository-local safety cap therefore consumes **zero** Deep Dive per-run slots and zero run-local Gemini slots.
- A model rejected by Persistent Safety Cap is marked session-exhausted, so later candidates in the same run do not repeatedly probe the same exhausted model.
- Pending Retry has an independent actual-send cap: `GEMINI_PENDING_RETRY_REQUEST_BUDGET=2` per Daily run. Old retries cannot consume the full Fresh-candidate Deep Dive budget.
- Quality Retry is skipped for non-repairable evidence/source gaps such as primary evidence insufficiency, unresolved primary source/freshness, and unsupported high-risk actions. Repairable wording/fact/structure issues remain eligible for the existing single retry.
- Gate history stores generation-attempt truncation history. Any `MAX_TOKENS` event remains visible in the final Funnel even if a later retry ends with another reason.
- These changes do not weaken Fact/Evidence/Publication/Human Appeal gates and add no new Gemini calls. Their purpose is to avoid requests or local budget consumption that cannot improve article quality.

## Real Article Quality Gate calibration

- 2026-08-21の実記事4ケース（AI Post-Training / latent multi-agent communication / Rust arrayref / Harness Continual Learning）から、GateのFalse PositiveとFalse Negativeを一般化してRegression化した。固有タイトルやURLの例外処理は追加していない。
- Geminiへ送るPrompt contextは従来の12,000文字上限を維持し、Fact/Evidence Gateだけが最大`VERIFICATION_CONTEXT_MAX_CHARS=180000`の`verification_context`を参照する。追加Gemini requestは0。
- Verification contextは長文の冒頭だけでなく末尾も保持し、後から取得した論文PDF/公式Docsへ専用枠を確保する。Landing pageが上限を埋めてもSupplement PDFが監査対象から消えない。
- Numeric Fact照合は`10-hour`/`10時間`、`50–80 percent`/`50〜80%`、`3–7x`/`3〜7倍`等を正規化する。Range内部の`80%`を別claimとして二重Failしない。
- LOW RISK ActionとSource Factを分離し、`Cargo.lock`等のローカル監査成果物は一次資料への逐語一致が無いだけでFact FAILにしない。一方、未根拠の外部製品能力（例: 未確認のEnterprise Sync）はAction文でも引き続き拒否する。
- `LLM API`等、一般略語だけを組み合わせた語を未確認の固有製品名として誤Failしない。
- Human Appeal Gateは架空の職務経験・使用体験・感情を検出する。`私なら`/`私の見解では`等の編集判断は許可し、読者への経験質問は筆者体験と混同しない。
- arXiv等の`future work`だけでは製品Freshness follow-upを発火しない。release / availability / support等、後から状態が変わる明示的予定だけを追跡する。
- Gate閾値は一律に緩和していない。実在Evidenceの見落としを減らす一方、架空体験のFalse Negativeを新たに止める校正である。

## Required deployment setting

- `GEMINI_QUOTA_PROJECT_ID` is optional audit metadata. Workflow accepts Repository Variable or Secret and otherwise uses `github.repository` as the safety-counter scope. See `GEMINI_QUOTA_SETUP.md`.
- `SUBSCRIPTION_LANDING_URL` may remain unset; subscription CTA/attribution stays disabled without affecting Daily article generation.


## Decision Intelligence Phase 1 validation

- Existing Internal Pipeline DB remains the article-state source of truth; no existing property is renamed or redefined.
- `Decision Score` is preserved. `Adoption Score` / `Adoption Status` are independent product-only management fields generated inside the existing Deep Dive Gemini request; no additional Gemini request is introduced.
- Product persistence is feature-flagged (`ENABLE_DECISION_INTELLIGENCE_DB=false` by default) and schema-preflighted before Gemini use when enabled.
- Technology Intelligence DB uses conservative Canonical Entity ID upsert; fuzzy-title merge is prohibited.
- Re-evaluation accumulates Source / Entity Alias / Evidence rather than overwriting prior signals.
- Decision History uses `History Event ID` for idempotent retry after partial Notion failures. CHANGE identity includes previous `Last Change At`, so a later repeated transition is not mistaken for a retry.
- New current records use `HISTORY_PENDING` until INITIAL History is durable. If evaluation changes during recovery, INITIAL is reconstructed from the pending current record and the new assessment is appended as a separate CHANGE.
- Legacy migration is dry-run by default, reads Internal DB only, never copies legacy Decision Score into Adoption Score, and seeds `LEGACY_PENDING`.
- Decision Intelligence persistence failure is isolated from article Ready/Review/Quality Failed state; existing article quality behavior remains unchanged.
- Migration workflow is manual-only and uploads its plan as a private Actions artifact.

## 2026-08-21 Notion Token Isolation Addendum

- Existing Internal DB token: `NOTION_API_KEY`
- Decision Intelligence product DB token: `NOTION_DECISION_INTELLIGENCE_API_KEY`
- No implicit fallback from product DB token to Internal DB token.
- Legacy migration reads the Internal DB with `NOTION_API_KEY` and performs Technology / History DB preflight/query/write operations with `NOTION_DECISION_INTELLIGENCE_API_KEY`.
- Dedicated token regression: 33/33 PASS.
- Full unittest discovery after token isolation: 295/295 PASS.
- Synthetic Regression Full after token isolation: 500/500 PASS, critical 0, production writes disabled.
- Workflow YAML: 5/5 PASS.
- `decision_intelligence.py` / `migrate_decision_intelligence.py` requests timeout missing: 0.
- `pipeline.py` top-level duplicate definitions: 0.


## Migration Entity Resolution hardening addendum
- Unit: 303/303 PASS
- Python syntax: PASS
- New migration invariants: generic article URL remains ambiguous; title-only/different-URL ambiguous rows never merge; same-source + normalized Primary URL exact duplicates may collapse only as migration dedupe while remaining AMBIGUOUS; blank URLs remain page-scoped; legacy tracking paused/not eligible; audit artifact exposes projected null Adoption fields
- Synthetic Full: 500/500 PASS, critical 0. Local run used the repository-equivalent google-genai import-only test stub; validator remained offline and performed no model/network/Notion writes. GitHub dry-run remains required before apply because only GitHub has the real Notion secrets/environment.
