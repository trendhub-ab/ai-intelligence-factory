# Daily Run 97 Stability Fix Validation — 2026-08-21

## Scope

Production Daily log (run 97) exposed two independent operational issues while the article safety gates themselves behaved correctly:

1. Deep Dive provider failures / local run-cap exhaustion could be surfaced as generic `MODEL_UNAVAILABLE`, and later Backfill candidates could still be entered even when no Deep Dive request could be sent.
2. A Quality Retry rewrites the full Gemini structured response. A retry that improved the free-note manuscript but dropped or degraded Decision Intelligence fields could erase an independently valid Adoption Assessment from the previous generation attempt.

This patch changes only those two control paths. Article quality thresholds and Decision/Adoption semantics are unchanged.

## Fix A — Deep Dive terminal stop semantics

- Added `DeepDiveRunBudgetExceededError` and reason code `DEEP_DIVE_RUN_BUDGET_EXHAUSTED`.
- Deep Dive run budget and Pending Retry budget are checked **before** `GEMINI_DEEP_DIVE_CALL_PACING_SECONDS` sleep and before provider invocation.
- A Deep Dive local run-cap stop is propagated as a budget stop and is never converted to `NoAvailableModelError`.
- The Fresh Backfill loop stops before entering another candidate when `DEEP_DIVE_MODEL_BUDGET` is exhausted.
- Pending Retry and Fresh Backfill loops also stop when every configured Deep Dive model is already marked run-local exhausted/unavailable.
- No change to provider retry count, model fallback order, persistent daily counter, or 429 handling.

Expected effect: no 20-second pacing, no fallback-model walk, and no extra Pending Retry candidates after a terminal run-local stop.

## Fix B — Decision Intelligence Assessment retention across Quality Retry

- Each generated structured response is independently validated with the existing strict `validate_decision_intelligence_assessment` validator.
- The newest valid Adoption Assessment + its validated evidence-state snapshot is retained in memory for that candidate.
- A later valid Quality Retry replaces the retained snapshot.
- A later invalid Quality Retry **cannot erase** the prior valid snapshot.
- At final side-path persistence, the current assessment is preferred when valid; otherwise the most recent retained valid assessment is revalidated and used.
- No extra Gemini request is introduced.
- Article Quality Gate outcome remains independent: a Quality Failed / Needs Editorial Review article can still store a valid subscriber-facing Adoption Assessment, exactly as Phase 1 intended.
- Invalid / unsupported Adoption Assessments still fail closed.

## Regression validation

- Targeted new tests: PASS
  - Deep Dive 0-remaining budget stops before pacing/provider call.
  - Deep Dive run-cap error is not misclassified as `NoAvailableModelError`.
  - Fully unavailable/exhausted Deep Dive model pool is detected before the next candidate.
  - Invalid Quality Retry reuses the previous valid Adoption Assessment.
  - Valid Quality Retry replaces the previous snapshot.
- Decision Intelligence unit suite: **43/43 PASS**.
- Full unittest discovery: **308/308 PASS**.
- Synthetic Regression Full: **500/500 PASS, critical failures 0**.
- Python compile: PASS (`pipeline.py`, `decision_intelligence.py`, `migrate_decision_intelligence.py`, `regression_suite.py`).

Synthetic Full was executed offline with an import-only `google.genai` test stub because the local artifact environment has no network access to install the SDK. The 500 fixture validator performs no provider, Notion, image, or publishing writes.

## Production invariants preserved

- Internal Notion DB remains the article-state source of truth.
- `Decision Score` remains independent from `Adoption Score`.
- Four Quality Gates are unchanged and are not relaxed.
- `Final >= 60` Stock rule is unchanged.
- Deep Dive per-run safety cap remains 12 requests by default.
- Pending Retry request cap remains 2 by default.
- Persistent Gemini daily safety counters remain unchanged.
- Decision Intelligence remains a feature-flagged side-path and its persistence failure cannot change article Ready/Review/Quality Failed outcome.
- Legacy Migration / Entity Resolution logic is unchanged.

## Next production check

Run the normal Daily workflow once with the existing production limits. Confirm:

1. If Deep Dive reaches `12/12`, the next Backfill candidate is not attempted and the log shows `[DEEP DIVE STOP] run budget exhausted...`.
2. If every Deep Dive model becomes run-local unavailable/exhausted, the next Backfill candidate is not attempted.
3. When a first generation has a valid Adoption Assessment and Quality Retry degrades only DI fields, the log shows `[DECISION INTELLIGENCE RETAINED]` and Technology Intelligence persistence can still proceed without another Gemini request.
4. Any genuinely invalid Adoption Assessment still logs `[DECISION INTELLIGENCE SKIP]`.
