# Saved X candidate -> Factory bounded validation

## Purpose

This lane closes the missing orchestration gap identified by the 2026-09-11 offline validation without turning X Discovery into a production acquisition source.

It is intentionally limited to one explicitly saved candidate and stops at the installed Factory screening prompt boundary.

## Entry point

The only root entry point is `production_pipeline.py` with:

- `AIIF_ONE_SHOT_MODE=x_saved_candidate_validation`
- `AIIF_X_SAVED_CANDIDATE_PATH=/path/to/one_saved_candidate.json`

The lane is selected only after the canonical runtime layers and current overlays are installed. It exits before normal runtime-state preflight, font download, performance telemetry, Daily acquisition, screening provider calls, generation, persistence, or publication.

## Allowed operation

Exactly one external Factory operation is permitted: the existing authoritative Notion deduplication READ through `pipeline.get_existing_repo_urls()`.

If that read fails or returns `None`, the lane fails closed. The candidate is also rejected if its canonical URL already exists in Factory.

Telegram alert delivery is temporarily suppressed only around this validation dedup read so a simulated or real dedup outage does not create a validation-side external notification.

## Explicitly forbidden

- Apify calls
- FetchLayer calls
- official X API calls
- primary-source HTTP/page fetches
- redirect resolution
- Gemini/model calls
- screening execution
- global calibration
- Evidence promotion
- Notion writes or page creation
- article generation
- eyecatch generation
- note draft creation/update
- publication

## Input contract

The JSON input must contain exactly one `candidate` object and one already-saved `prepared_primary_source` object. X remains `discovery_only` and `is_evidence=false`. The saved primary-source URL must canonicalize to the same URL as the candidate, and the saved source text must be non-empty and at least 200 characters.

X engagement is never copied into Factory engagement or scoring fields. The mapped screening candidate uses `stargazerCount=0` and keeps X post ID / post URL / author only under `x_discovery_provenance`.

## Successful result

A successful dry validation returns `status=SCREENING_BOUNDARY_READY` and a SHA-256 hash of the real installed Factory batch-screening prompt. It also asserts:

- candidate_count = 1
- dedup_verified = true
- screening_executed = false
- model_calls = 0
- source_fetch_calls = 0
- apify_calls = 0
- fetchlayer_calls = 0
- factory_write = false
- evidence_promoted = false
- generation_executed = false
- publication_executed = false

This is not a quality score, publication approval, or authorization for a live screening/model request.

## Next gate

Only after this lane is verified against the saved Defense Factory candidate should a separate bounded model trial be considered. That later trial must define a total request ceiling before execution; screening, calibration, generation, retries, and quality repair must not be treated as one request.
