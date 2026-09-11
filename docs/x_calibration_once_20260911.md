# Defense Factory: one Calibration operation

The saved candidate and second saved Screening observation (Raw 88) enter through
`production_pipeline.py`, mode `x_saved_candidate_calibration_validation`.
The default remains a zero-provider prompt boundary. Explicit execution additionally
requires the fixed operation ID `defense-factory-calibration-20260911`.

Before Gemini, a create-only marker is committed at
`runtime-state:.runtime/operations/defense-factory-calibration-20260911.json`.
The claim has no expiry or automatic release. Duplicate processes, workflow reruns,
timeouts and ambiguous outcomes must stop without reissuing the operation.
The existing persistent daily counter remains independently authoritative; this
repository-local counter does not establish the provider's billing tier or balance.

Only `gemini-3.5-flash-lite` is allowed, with a fresh process budget of one request.
The production quota-aware `_generate_via_chat` is used directly, avoiding model-pool
retry/fallback logic. SDK HTTP attempts are fixed at one and automatic function
calling is disabled. The original saved inputs are pinned by SHA-256.
Missing or invalid responses do not produce a Final Score or reuse Raw as Final.

No Screening repeat, source fetch, Notion write, article generation or publication
is performed. A real Final is checked by the existing pure Stock/Deep Dive selector
with persistence false. Crossing the score threshold cannot grant Deep Dive access.

Validation: 13 offline tests pass, including an installed-production entrypoint test
whose mocked HTTP transport returns 503 and records exactly one SDK HTTP attempt.
Mocked transport attempts are not real Gemini requests.

The dedicated workflow has a single push trigger on the exact validation branch and
workflow path, no PR/dispatch trigger, run-attempt=1, and the existing Gemini-budget
concurrency group. The durable claim, not workflow serialization, enforces the total
operation ceiling. Results/failures are retained as Actions artifacts. Do not delete
the claim or create another operation ID to retry this authorization.

## Observed result

[Actions run 34600579532](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/34600579532)
completed successfully at 2026-09-11 12:45 UTC. Job 103266586342 records one live
HTTP 200 response. The separate offline test's HTTP 503 was a mocked transport.

- Raw 88 -> Final 88; commercial 90; shelf-life 80; topic SECURITY.
- Model: gemini-3.5-flash-lite; prompt 599 tokens, output 119, total 718.
- Operation total: one real Gemini attempt, no retry or fallback.
- Shared counter changed used 4 -> 5, global_calibration 0 -> 1;
  x_saved_screening_validation stayed at 4. These are repository-local counts.
- Stock threshold 60 passed, but no Stock/Notion content was persisted.
- The real pure Deep Dive selector rejected the unpersisted candidate.
- No source fetch, Apify, FetchLayer, article generation or publication.

The parsed response and provenance are preserved in
`x_discovery/observations/defense_factory_calibration_20260911.json` and
[Actions artifact 10264421063](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/34600579532/artifacts/10264421063).
The temporary push workflow is removed after this completed proof. Its executed
source remains in commit 9d8ba7bdf33dee2b9098454c7ed5cb70f6a9771d.
The durable operation claim remains in runtime-state and must not be removed.

Next: a separate, explicitly scoped Stock persistence step; no further Calibration
is needed to repeat this observation. Article generation/publication are not authorized
by this result.
