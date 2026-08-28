# Run131 — Profit-Aligned Portfolio Intelligence

## Why Run131 exists

Run130 fixed a real product defect: the paid inventory could become a proxy for discovery-source composition, especially GitHub OSS. A subsequent adversarial audit found two remaining defects:

1. Run130 affected manual Subscriber Inventory Bootstrap, but normal Daily Product Review still used the legacy Screening-Score order.
2. The 45% source-share cap could act as a hard quota and force a materially weaker candidate upward, contradicting the product principle that quality / decision value must dominate diversity.

Run131 closes both gaps without changing Adoption, Evidence, article Quality Gates, Notion persistence, or Gemini accounting.

## Business rule

Portfolio diversity is valuable only when candidate quality is close.

- The strongest remaining candidate defines the commercial/decision-value reference point.
- Candidates within `PORTFOLIO_DIVERSITY_TOLERANCE` (default 8 points) may be reordered to reduce repeated source/category/lane/layer concentration.
- A candidate outside that tolerance cannot be promoted merely to improve the mix.
- There is no hard source quota.
- Product Hunt is discovery only; Product Hunt membership alone never makes a record `APPLIED_AI`.
- Multi-source records are counted by their complete source set, not `source[0]`.

## Three portfolio layers

- `APPLIED_AI` — directly usable product/service only when product taxonomy or explicit technical product signals support it.
- `PRACTICAL_TECH` — agents, MCP, RAG/retrieval, security, data, inference, observability, infrastructure, multimodal, models, meaningful tooling.
- `DEEP_TECH` — research, mechanisms and architectures with future decision value.

These are review-order concepts, not Adoption statuses and not forced quotas.

## Daily integration

Run131 deliberately avoids invasive edits to `pipeline.py`.

Daily now runs in two sequential passes under the same GitHub Actions concurrency lock and persistent Gemini accounting:

1. **Normal article pass** — acquisition, screening, calibration, Stock, Deep Dive, article quality, monthly logic. Product Review is set to `PRODUCT_REVIEW_MAX_PER_RUN=0` in this pass.
2. **Portfolio Product Review pass** — `daily_portfolio_review.py` reads the just-updated Technology Intelligence DB with zero Gemini calls, builds a tolerance-protected ordered allowlist, then invokes the existing pipeline in its already-tested product-only `INVENTORY_BOOTSTRAP_ACTIVE` mode.

The second pass therefore reuses the existing authoritative Product Review implementation for Evidence, Adoption assessment, History, Subscriber sync and request-budget enforcement.

`HISTORY_PENDING` remains first because it is state-integrity recovery. All other eligible `SCREENED`, due `ASSESSED`, and resolved due `LEGACY_PENDING` records compete in the same portfolio pool. There is no reserved weak legacy slot after launch.

## Text classification hardening

Run131 uses token/phrase boundaries for planning taxonomy and product/lane signals. Short terms such as `rag` and `app` no longer match accidental substrings such as `ragged` or `application`.

Authoritative non-`OTHER` Category remains untouched. Planning inference never mutates the database category.

## Manual Bootstrap

`portfolio_inventory_bootstrap.py` continues to install the portfolio overlay over the mature manual Bootstrap path.

The old `--max-source-share` parser argument remains accepted internally for backward compatibility, but Run131 ignores it. The workflow no longer exposes or passes a hard source-share input. `PORTFOLIO_DIVERSITY_TOLERANCE=8` is the active control.

## Safety / cost

Run131 adds no Gemini call site.

- Candidate ranking is local Python only.
- Normal Daily Product Review calls are moved, not duplicated.
- The portfolio Product Review pass retains the existing maximum of 2 evidence-ready reviews and local request budget of 3.
- Existing persistent daily model counters remain authoritative.
- Existing Evidence, assessment validation, History, Subscriber synchronization and fail-closed behavior are reused.

## Acceptance criteria

- materially weaker candidates cannot be source-diversity promoted;
- Product Hunt alone cannot classify `APPLIED_AI`;
- technical term matching is boundary-safe;
- source tuple ordering cannot change portfolio score/layer;
- Daily Product Review uses the Run131 ordered allowlist;
- article pass does not also run Product Review;
- no new Gemini client/call site is introduced;
- Run130/Inventory/Run110 regressions remain green.
