# Run304 — Product Review Runtime-State Counter Handoff

Date: 2026-09-09

## Observed Production failure

Run37 proved Run303 provider-503 recovery in live Production. During the same run, the separate Portfolio-aware Product Review child printed `Persistent Gemini Daily Counter(scope=3fc8d874): 0` even though the immediately preceding Production process had non-zero current counts.

The parent ONE-SHOT process had already persisted current Gemini usage on the `runtime-state` branch. `daily_portfolio_review.py` then spawned `pipeline.py` directly. That child inherited the stale `GEMINI_COUNTER_BRANCH=main` value, while the authoritative branch name was available separately as `AIIF_RUNTIME_STATE_BRANCH=runtime-state`. Because the child does not execute `production_pipeline.py`, it does not install the runtime-state overlay by itself.

## Fix

`daily_portfolio_review._run_product_only` now checks `AIIF_RUNTIME_STATE_BRANCH` immediately before spawning the product-only child. When present, the child receives that value as `GEMINI_COUNTER_BRANCH`, so it reads the same authoritative persistent counter as the parent Production process.

If no runtime-state overlay exists, an explicit operator-supplied `GEMINI_COUNTER_BRANCH` is preserved. This keeps standalone/testing operation backward-compatible.

## Non-changes

- Gemini per-model daily safety ceilings are unchanged.
- Product Review max-review/request budgets are unchanged.
- Deep Dive/Pending Retry budgets are unchanged.
- Fact, Evidence, Decision, Publication, Human Appeal gates are unchanged.
- Scheduled Daily remains PAUSED.
- Public note release remains human-only.

## Regression contract

`tests/test_run304_product_review_counter_state.py` verifies:

1. `AIIF_RUNTIME_STATE_BRANCH=runtime-state` overrides a stale child `GEMINI_COUNTER_BRANCH=main`.
2. Without a runtime overlay, an explicit operator counter branch is preserved.
3. Zero request budget remains terminal and cannot spawn the Product Review child.

This change fixes accounting/state authority only. It does not increase API budget or relax quality gates.