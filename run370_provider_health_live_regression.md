# Run370 Production Regression Evidence

Source: manual Production ONE-SHOT Run #57 (`34960258718`) on main `e2bae6baab8eed203ae7c93db57f2234628f3bee`.

Observed provider sequence on the recovery article:

- gemini-3.6-flash: HTTP 503 -> run-local unavailable
- gemini-3.5-flash: HTTP 503 -> run-local unavailable
- gemini-3.7-flash: HTTP 200 -> generation succeeded
- subsequent Quality Retry: `NoAvailableModelError` before reaching the healthy 3.7 fallback

The reproduced cause is ordering of operations, not a reason to relax any content gate: the Quality Retry pool was truncated to the historical Health top two before run-local unavailable models were removed. In the same live run, Provider Health telemetry also failed to append the new attempts to `runtime-state/.runtime/gemini_provider_health.json` because the later Run172 provider wrapper had replaced Run260's `_call_model_pool` capture point.

Run370 changes only routing/telemetry placement. All Fact, Evidence, Publication, Human Appeal, Reader, request-budget, persistent-RPD and scheduled-Daily safety contracts remain unchanged.
