# Run238 — Deep Dive Portfolio Modularization

## Purpose

Run238 continues the zero-quality-change slimming of `pipeline.py` by extracting the deterministic Deep Dive portfolio-shaping surface into `deep_dive_portfolio.py`.

This Run is a structural ownership change only. It does **not** change article generation, Gemini requests, Screening/Deep Dive budgets, Fact/Evidence/Decision thresholds, Publication/Human Appeal gates, Notion schema, Daily PAUSED, or human-only public note release.

## Canonical ownership

`deep_dive_portfolio.py` is the canonical owner of:

- `topic_counts()`
- `apply_content_portfolio_balance()`
- `publication_probability_score()`
- `apply_publication_reliability_slot()`
- `select_stocked_deep_dive_candidates()`

`pipeline.py` keeps compatibility wrappers with the historical names and passes all live runtime flags, thresholds, normalizers, metadata attachers, logger, and nested wrapper callbacks on every call.

## Protected behavior

Run238 preserves the existing contracts exactly:

1. Only persisted Stock at or above the existing Notion save threshold is eligible for Deep Dive ordering.
2. Profit priority only reorders already-eligible Stock; it cannot bypass Decision/Evidence/Fact eligibility.
3. Topic diversity may promote only a near-peer candidate within the existing tolerance.
4. `OTHER`/unknown topic metadata remains fail-safe and does not force a diversity reorder.
5. The existing EVERGREEN minimum and priority tolerance remain unchanged.
6. Publication reliability remains a metadata-only zero-model proxy and can occupy only the existing configured slot when the existing Decision threshold and advantage conditions are met.
7. The historical non-profit fallback sort remains Decision Score then GitHub stars, descending.

## Provider and persistence boundary

The extracted module is stdlib-only. It does not import or initialize:

- Gemini / Google GenAI
- `requests`
- Notion clients
- credentials or environment state
- filesystem/network persistence

The pipeline wrapper remains responsible for binding live Production dependencies.

## Physical slimming

Guarded migration result:

- `pipeline.py`: **13,244 -> 13,112 lines**
- bytes: **755,724 -> 749,659**
- migration diff: **43 insertions / 175 deletions** in `pipeline.py`

The heavy algorithm bodies were physically removed from `pipeline.py`; only live-binding compatibility wrappers remain.

## Falsification contract

Permanent CI must prove:

- `deep_dive_portfolio.py` remains provider/persistence-free.
- `pipeline.py` contains only thin wrappers for the five extracted surfaces.
- wrapper aliases point to the canonical module functions.
- live runtime flags/tolerances/thresholds are read at call time.
- materially weaker candidates cannot be promoted for diversity.
- `OTHER` metadata remains fail-safe.
- publication reliability threshold/advantage behavior remains unchanged.
- existing Run131 profit-aligned portfolio tests remain green.
- full pytest and Synthetic smoke remain green before merge.

## Out of scope

Run238 intentionally does not extract or modify:

- `run_product_reviews()` or Product Review model parsing/generation
- `process_article_backlog()`
- deferred Deep Dive queue persistence
- collection/screening
- article drafting/rescue/gates
- Gemini quota accounting

These remain separate future slimming candidates and require their own falsification scope.
