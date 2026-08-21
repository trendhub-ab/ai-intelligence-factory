# AI Intelligence Factory Release Validation

Release: Gemini Quota Repository Scope / Usage Audit修正版 2026-08-21

## Final validation

- Python syntax: PASS
- Safety Unit: 76/76 PASS
- Notion Persistence: 48/48 PASS
- Adversarial / Failure Injection: 106/106 PASS
- Subscription Attribution: 11/11 PASS
- unittest discovery: 241/241 PASS
- Synthetic Regression Full: 500/500 PASS
- Critical failures: 0
- Workflow YAML parse: 4/4 PASS
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

## Required deployment setting

- `GEMINI_QUOTA_PROJECT_ID` is optional audit metadata. Workflow accepts Repository Variable or Secret and otherwise uses `github.repository` as the safety-counter scope. See `GEMINI_QUOTA_SETUP.md`.
- `SUBSCRIPTION_LANDING_URL` may remain unset; subscription CTA/attribution stays disabled without affecting Daily article generation.
