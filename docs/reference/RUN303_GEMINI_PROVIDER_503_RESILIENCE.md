# Run303 / Run398 — Gemini Provider HTTP 503 Resilience

## Why this contract exists

Production ONE-SHOTs reproduced genuine Google GenAI HTTP `503 Service Unavailable` responses. The original Run303 fix added provider-verified handling so text that merely contains `503` is never mistaken for a structured provider status, and so retry/fallback remains bounded by Factory budgets.

Later Production evidence showed that the same-model confirmation retry was too expensive for the canonical Flash Deep Dive pool: with a four-request validation budget, 3.8×2 + 3.7×2 could consume all requests before 3.6 / 3.5 were tried. Run398 therefore narrowed the current Production contract for canonical Deep Dive and Pending Retry.

Run360 additionally establishes a single retry owner. google-genai internal transient retries are disabled with SDK attempts=1; Factory routing/circuit logic owns every retry or fallback decision.

## Current Production contract

`gemini_provider_resilience.py` is authoritative for model-pool provider transport handling after the Production routing overlays are installed.

### Structured status only

- HTTP status is read only from structured numeric exception fields such as `exc.code` or `response.status_code`.
- Exception text containing `503` is insufficient.
- Transport timeout is a separate failure class and does not confirm an HTTP 503 circuit.

### Canonical Flash Deep Dive

For the canonical article models:

- `gemini-3.8-flash`
- `gemini-3.7-flash`
- `gemini-3.6-flash`
- `gemini-3.5-flash`

one structured HTTP 503 is enough to stop spending on that model for the current run and preserve the next request for the next distinct model.

There is **no same-model 503 confirmation retry** in this canonical Deep Dive path. A sequence such as 3.8=503, 3.7=503, 3.6=success therefore uses exactly three provider-visible model sends.

Pending Retry follows the same budget-preserving one-503 fallback behavior, while its own total provider-send ceiling remains authoritative.

### Ready Rescue

Ready Rescue is stricter: a provider HTTP error ends that rescue attempt with **no retry and no fallback**. Rescue cannot consume additional models after the first provider failure.

### Screening, Product Review and noncanonical/custom pools

The historical bounded confirmation behavior remains for paths that are not covered by the canonical Run398 Deep Dive rule:

- the first structured 503 may receive exactly one same-model confirmation retry;
- the retry delay uses the existing retry-delay extractor, defaults to 10 seconds, and is capped at 20 seconds;
- a second consecutive structured 503 opens the run-local circuit and routing moves on;
- Product Review remains separately request-budgeted.

### Other failure classes

- 404 / unsupported model: mark run-local unavailable and move on.
- 429 RPD or daily-token exhaustion: mark that model exhausted.
- 429 RPM / TPM: at most one bounded retry according to the existing delay contract.
- transport timeout: fall back without classifying it as HTTP 503.
- persistent model budget exhaustion: remains authoritative and fail-closed.

### Retry ownership and budgets

- google-genai SDK retry attempts: **1**.
- retry owner: **Factory**.
- Factory request budgets, per-model persistent daily budgets, Pending Retry budget, Product Review budget and Deep Dive budget remain authoritative.
- A provider retry/fallback never creates an unbounded request lane.
- Fact / Evidence / Publication / Reader gates are unchanged by provider transport handling.

## Health routing

Run370 ranks the usable article pool using recent provider success/error telemetry stored on the dedicated runtime-state branch. It filters current run-local unavailable/exhausted models before applying the Quality Retry two-distinct-model ceiling. Health telemetry is operational state only; it does not contain prompt or article content and a telemetry read/write failure does not block article generation.

## Falsification coverage

- `tests/test_gemini_provider_resilience.py`: structured status classification, bounded confirmation behavior for noncanonical paths, timeout separation, budgets and Product Review.
- `tests/test_run398_gemini_503_fallback.py`: canonical Deep Dive one-503-per-model fallback and low-thinking contract.
- `tests/test_run370_provider_health_live_regression.py`: health-ranked live routing and unavailable-model filtering.
- `tests/test_pending_validation_model_exclusions.py` / `tests/test_temporary_provider_exclusion.py`: Pending Retry provider guard, send ceiling, and expiry-bound temporary exclusions.

No article-quality threshold, Evidence rule, Decision rule, Notion schema, member presentation rule, or note publication rule is relaxed by this contract.
