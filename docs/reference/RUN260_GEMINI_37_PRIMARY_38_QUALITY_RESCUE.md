# Run260 — Gemini 3.7 Primary / 3.8 Quality Rescue

Date: 2026-09-06

## Why

The 2026-09-06 full ONE-SHOT completed successfully but produced zero Ready articles. The result included Editorial Review / Quality-Fact blocks plus provider 503 Pending Retry cases. The correct response is not to lower Fact, Evidence, Publication, or Reader gates merely to force output.

Google made `gemini-3.8-flash` generally available on 2026-09-02. The Gemini API model page marks it Stable/GA and the Gemini API pricing page lists a Free Tier as free of charge. Google also notes that higher reasoning effort can use more tokens and that occasional slowness/timeouts can occur. AI Studio project-visible rate limits remain the operational source of truth.

## Production routing contract

Article-side Production only:

- Fresh Deep Dive primary: `gemini-3.7-flash`
- Fresh Deep Dive fallback order: `gemini-3.8-flash` -> `gemini-3.6-flash` -> `gemini-3.5-flash`
- Existing model-based `quality_retry`: prefer `gemini-3.8-flash`, then `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.7-flash`
- Screening remains unchanged: Flash-Lite pool only.
- Existing zero-API deterministic rescue remains unchanged and stays ahead of any unnecessary provider call.

The routing layer reorders only an already-authorized `_call_model_pool` invocation. It does **not** create a new retry loop or provider-call path.

## Cost / quota contract

Unchanged:

- Deep Dive per-run cap: 12 real provider attempts.
- Pending Retry budgets remain authoritative.
- Existing process-wide request budget remains authoritative.
- Existing 503 cooldown / fallback remains authoritative.
- 404 / RPD / timeout fail-closed behavior remains authoritative.

New:

- `gemini-3.8-flash` is added to the repository-local persistent counter at a conservative maximum of 18 requests/day.
- Optional `GEMINI_38_FLASH_DAILY_BUDGET` may lower this value but Run260 clamps it to 18 and never lets that variable raise the established Flash safety ceiling.

The 18 value is a Factory safety cap, not a claim about Google's universal account quota. Google AI Studio's current Project-wide limit is the final external truth.

## Quality contract

Run260 does not change:

- Fact Gate
- Evidence Gate
- Source Score / primary-source requirements
- Publication Gate
- Reader Value / Human Appeal thresholds
- Decision logic
- article output-count target
- public note release policy

A candidate that still fails after the bounded repair path remains non-Ready.

## Operational contract

- Scheduled Daily remains PAUSED.
- Public note release remains human-only.
- No Gemini API call is required to validate this code change; CI/regression is zero-API.
- Product Review routing is not intentionally changed by Run260; the article production runtime layer owns this upgrade.

## Official references checked 2026-09-06

- Gemini API latest model: https://ai.google.dev/gemini-api/docs/latest-model
- Gemini 3.8 Flash model page: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Google DeepMind model card: https://deepmind.google/models/model-cards/gemini-3-8-flash/
