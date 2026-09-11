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

Execution outcome: pending. This document does not claim a real Calibration result.
