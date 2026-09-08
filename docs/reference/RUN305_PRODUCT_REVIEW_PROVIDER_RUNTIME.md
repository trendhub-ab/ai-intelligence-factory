# Run305 — Product Review Provider Runtime

Date: 2026-09-09

## Problem observed in real ONE-SHOT Run38

Run304 correctly handed the authoritative `runtime-state` Gemini persistent counter to the Product Review child. Run38 proved the counter bug fixed: the child read the live non-zero counter and advanced `gemini-3.6-flash` from 5/18 to 8/18 while saving two Product Review records.

The same live run exposed a separate provider-resilience gap. The Product Review child was launched as raw `pipeline.py`, while the normal Production path is launched through `production_pipeline.py` and installs the runtime reliability stack. Therefore Product Review did not install Run209 timeout/RPD fail-closed handling, transient recovery, or Run303 provider-verified HTTP 503 confirmation handling.

Concrete Run38 evidence:

- Product Review `gemini-3.6-flash` first review: HTTP 200.
- Second Product Review request: HTTP 503.
- No `[PROVIDER HTTP 503]` / `[PROVIDER HTTP 503 RETRY]` marker appeared in that child path.
- The flow later entered the logical `product_review_retry` request and succeeded, showing that the direct child had bypassed the Run303 wrapper rather than exercising its same-model confirmation contract.

This was an installation-path defect, not a defect in the Run303 algorithm. `tests/test_gemini_provider_resilience.py` already verifies that Run303's Product Review wrapper performs `503 -> same model confirmation retry -> success` correctly when installed.

## Fix

Run305 adds `product_review_runtime.py` and routes `daily_portfolio_review.py` through it instead of launching raw `pipeline.py`.

The Product Review child installs only the provider/quota reliability layers required for safe provider access, in this order:

1. `run203_runtime_state_channel.install`
2. `gemini_timeout_rpd_fail_closed.install`
3. `gemini_transient_recovery.install`
4. `gemini_provider_resilience.install`

It then calls `pipeline.main()` in the existing product-only environment.

## Deliberately not installed

Run305 does **not** install `run260_gemini_model_routing` in the Product Review child. Product Review intentionally uses its own configured order:

`gemini-3.6-flash -> gemini-3.7-flash -> gemini-3.8-flash -> gemini-3.5-flash`

That order protects article-generation capacity and must not be silently rewritten to the article Deep Dive order.

Run305 also does not install article/publication/Reader Value/eyecatch layers. Product Review remains a bounded paid-product maintenance path, not an article-generation path.

## Preserved safety and business contracts

- `DAILY_PORTFOLIO_REVIEW_MAX`: unchanged; normal value remains 2.
- `DAILY_PORTFOLIO_REQUEST_BUDGET`: unchanged; normal value remains 3.
- Persistent per-model daily safety caps: unchanged.
- Run304 authoritative `runtime-state` handoff: retained.
- A first structured HTTP 503 gets at most one same-model confirmation retry, inside the existing Product Review budget.
- A second consecutive structured HTTP 503 opens the run-local circuit for that model.
- Timeout reservations remain fail-closed under Run209.
- No Fact/Evidence/Decision/Publication gate is weakened.
- Scheduled Daily remains PAUSED.
- Public note release remains human-only.

## Regression contract

`tests/test_run305_product_review_provider_runtime.py` verifies that:

- `daily_portfolio_review.py` spawns `product_review_runtime.py` rather than raw `pipeline.py`;
- the child still receives the authoritative runtime-state counter branch;
- only the four provider/quota layers are installed, in the intended order;
- Run260/Run172 are not introduced into the Product Review-specific runtime;
- provider layers are installed before `pipeline.main()`.

The existing Run303 Product Review regression remains authoritative for the actual structured-503 same-model retry semantics.
