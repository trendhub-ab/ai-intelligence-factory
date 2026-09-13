# Run412 — Approved available-model route

## Why

For the current owner-approved RubyGems apply, the operator confirmed remaining Gemini capacity of approximately two Gemini 3.8 Flash requests and thirteen Gemini 3.5 Flash requests. Gemini 3.7/3.6 should not be used for this execution.

## Contract

Run412 is active only when the explicit Run399 apply workflow sets `ARTICLE_REVALIDATION_AVAILABLE_MODEL_POOL`.

For the current execution:

- initial Deep Dive: `gemini-3.8-flash` → `gemini-3.5-flash`;
- quality / Reader repair: `gemini-3.5-flash` → `gemini-3.8-flash`;
- Gemini 3.7 and 3.6 are excluded from this approved run;
- existing per-model persistent counters remain authoritative;
- the existing per-run request budget remains 5;
- no Fact, Evidence, Reader, Human Appeal, Publication, or persistence Gate is relaxed.

## Scope

The override applies only to `candidate_origin=approved_article_apply`. Normal Daily, ordinary article validation, Pending Retry, Product Review, and X logic retain their existing routing.

If the workflow does not set the Run412 environment variable, the overlay is a no-op and historical routing remains unchanged.

## Publication boundary

A successful accepted article may proceed to Note Ready sync and private note draft creation. Public note publication remains manual and is not authorized by Run412.
