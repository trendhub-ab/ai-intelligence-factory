# Run303 — Gemini Provider HTTP 503 Resilience

## Why this change exists

Two consecutive real Production ONE-SHOT runs (Run35 `34239711523` and Run36 `34239850456`) reproduced genuine Google GenAI HTTP `503 Service Unavailable` responses. The 503s were not fabricated by text parsing: the SDK's HTTP log itself reported status 503.

The same evidence also falsified the stronger assumption that a model should be treated as unavailable for the rest of a run after sparse transient 503s. In Run36, `gemini-3.7-flash` returned HTTP 200 between HTTP 503 responses. The historical Run172 fail-fast wrapper moved to another model after the first 503, while `gemini_transient_recovery.py` accumulated 503 occurrences across the whole run without resetting after success. That combination could turn short provider instability into an apparent run-wide model outage.

A separate timeout audit found that Run209 correctly kept the persistent RPD reservation on transport timeout. The core logger still printed a stale message saying that the reservation had been released; this was an observability defect, not a counter rollback.

## Current Production contract

`gemini_provider_resilience.py` is installed immediately after `run172_production_reliability.py` and is authoritative only for model-pool provider transport handling.

- HTTP 503 is classified only from structured numeric exception status (`exc.code` or `response.status_code`). Exception text containing `503` is insufficient.
- The first verified HTTP 503 for a request gets exactly one same-model confirmation retry.
- The confirmation wait honors the existing retry-delay extractor, defaults to 10 seconds, and is capped at 20 seconds.
- Only a second consecutive verified HTTP 503 opens the run-local circuit for that model.
- A successful response, timeout, 429, 404, or another non-503 result breaks the 503 sequence and clears stale legacy cumulative state.
- Transport timeout is logged separately from HTTP 503 and does not increment/confirm the 503 circuit.
- Deep Dive, Pending Retry, Product Review, persistent per-model daily ceilings, publication gates, Fact/Evidence/Decision gates, and Daily PAUSED remain authoritative and unchanged.
- The confirmation retry is not a new unlimited lane: it consumes the existing request budgets and persistent daily safety counter.
- Run209 timeout reservations remain fail-closed. Run303 only corrects the stale post-timeout log when a standard logger filter is available.

## Falsification coverage

`tests/test_gemini_provider_resilience.py` verifies structured-vs-text classification, 503→200 same-model recovery, confirmed consecutive 503 fallback, timeout separation, stale-state reset, terminal request budgets, and Product Review behavior.

`tests/test_gemini_timeout_rpd_fail_closed.py` verifies that timeout reservation release stays suppressed and the stale legacy log is rewritten without changing accounting.

No article quality threshold, Evidence rule, Decision rule, source architecture, Notion schema, member presentation rule, or public-release policy is changed by Run303.
