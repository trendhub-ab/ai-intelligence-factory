# Run134 Revenue Measurement Foundation + Paid Product Value — Setup

## Business objective
Run133 article-generation behavior is frozen. Run134 connects the existing product system more directly to revenue learning and paid-member utility without adding Gemini calls, weakening Fact/Evidence gates, or feeding immature revenue data back into ranking.

## Proposal 1 — Revenue Measurement Foundation
`subscription_attribution.py` now produces schema v2 rollups with:
- article-level aggregate metrics retained; subscriber PII remains forbidden;
- source-level and portfolio-topic-level performance summaries;
- `revenue_measurement_readiness` with measured-article, views, clicks, subscribers, CTA coverage and end-to-end coverage diagnostics;
- `ranking_feedback_enabled=false` and `auto_feedback_permitted=false` remain fail-closed even when the sample threshold is reached.

Readiness means **human review may begin**, not that production ranking changes automatically. A future revenue-feedback release requires an explicit business decision and separate implementation.

Default diagnostic thresholds:
- measured articles >= 20
- note views >= 5,000
- CTA clicks >= 100
- new subscribers >= 20
- tracked CTA coverage >= 70% of measured articles
- end-to-end/manual-verified coverage >= 50%

These thresholds are sample-quality heuristics, not revenue targets.

## Proposal 2A — Paid Product Value Density
`inventory_bootstrap.py` adds deterministic `paid_product_utility()` diagnostics for sellable records. It checks whether Main Risk / Best For / Avoid For / Short Rationale are substantive rather than generic, whether Evidence exists, and whether Best For vs Avoid For are meaningfully differentiated.

`evaluate_readiness()` now reports `paid_product_value`:
- HIGH utility count
- MEDIUM+ utility count
- average utility score
- diagnostic blockers

This is **diagnostic only** in Run134. It does not change Adoption Score/Status and does not hard-block launch. This prevents a new heuristic from accidentally suppressing a commercially viable launch before live customer evidence exists.

Default value-density targets:
- HIGH utility >= 8
- MEDIUM+ utility >= 18

## Proposal 2B — Monthly Decision Brief
The existing monthly History product is upgraded from a change log to a deterministic decision brief.

Top section: `今月、何を再判断すべきか？`
- prioritizes status changes first, then meaningful score movement;
- uses only existing Decision History facts;
- labels current Adoption Status as an action-oriented member cue (ADOPT/TEST/WATCH/AVOID);
- never invokes Gemini and never invents a new Adoption decision.

The detailed legacy sections (status changes, rises, drops, new assessments) remain underneath for auditability. Notion Monthly DB schema is unchanged.

## Explicitly unchanged
- Run133 article prompt / Reader-First compression
- article Quality/Fact/Evidence/Source Boundary gates
- Product Review Gemini path/budget
- Adoption score/status/hysteresis
- Technology/Subscriber/History/Monthly Notion schemas
- Subscriber sanitization and Evidence Ledger isolation
- Source ROI and production ranking
- Gemini call sites

## Deployment
1. Apply Run134 to a test branch.
2. Run unit/pytest + Synthetic Regression in GitHub Actions.
3. Merge only after green.
4. Continue the planned Run133 fixed Real Article Regression after Gemini quota reset; Run134 does not alter article generation.
5. Populate aggregate subscription metrics as data accumulates; do not enable revenue ranking feedback yet.
