# V2-004 Provider-Backed Evidence Design

Date: 2026-10-14
Status: Approved for implementation
Base main: `3ddd3b24270e4b4a474c984cd98ecf4c8306d93e`

## Objective

Prove the smallest provider-backed Evidence / Deep Dive vertical slice for AIIF V2 without changing Production authority.

Invariant:

> V2 may ask one bounded evidence question about rank 1. V1 still decides and writes Production.

## Trigger path

Chat remains indirect and fail-closed:

`Chat -> Issue #71 exact owner comment -> AIIF ChatOps ONE-SHOT Bridge -> GH_PAT -> v2-shadow-deep-dive.yml`

Exact command:

`/aiif run v2_shadow_deep_dive`

The bridge never accepts an arbitrary workflow name, ref, model, prompt, or payload from the comment.

## Selection and provider boundary

1. Reuse V2-002 bounded public acquisition (Hacker News + arXiv metadata only).
2. Reuse V2-001 deterministic normalization, dedupe, cheap screening, and rank.
3. Only eligible rank 1 may reach Deep Dive.
4. Deep Dive request budget is exactly one attempt per run.
5. No retry and no rank-2 fallback.
6. No additional article/body fetch is introduced in V2-004.
7. The request uses only already acquired candidate fields: identity/URL, provider, title, description/abstract, source timestamp, and deterministic screening metadata.

## Model policy

V2-004 uses the first approved non-Lite Deep Dive model from the current Production policy: `gemini-3.6-flash`.

No Lite model is permitted. No model fallback is permitted in V2-004 because fallback would violate the one-request proof budget.

Only `GEMINI_API_KEY` is supplied to the V2-004 workflow. No Notion, note, GitHub write, publication, queue, Telegram, or Production persistence credential is supplied.

## Strict result contract

The provider response must decode to exactly:

```json
{
  "evidence_sufficient": true,
  "reason_code": "sufficient_source_evidence",
  "evidence_points": ["bounded factual point"]
}
```

Allowed `reason_code` values:

- `sufficient_source_evidence`
- `insufficient_source_evidence`

Validation is fail-closed:

- top-level value must be an object;
- exact keys only;
- `evidence_sufficient` must be a JSON boolean;
- reason code must be allowlisted;
- `true` must pair with `sufficient_source_evidence`;
- `false` must pair with `insufficient_source_evidence`;
- `evidence_points` must be a non-empty list of 1..5 non-empty strings;
- each point is bounded to 500 characters;
- malformed JSON, markdown fences, unknown keys, unknown reason codes, contradictory values, provider exceptions, or missing output fail closed.

V2-001 remains the winner authority inside the shadow slice: only exact `evidence_sufficient is True` can produce a V2 shadow winner candidate.

## Output and authority

The workflow writes only `article_audit/v2_shadow_deep_dive.json` and uploads it as a short-retention diagnostic artifact.

The report records:

- `observation.mode = provider_backed_one_shot`
- model name
- request budget = 1
- actual Deep Dive calls from V2-001
- strict parsed evidence result when valid
- Production authority = `v1`
- diagnostic-only marker

No prompt text, API key, transport exception message, or provider raw response is persisted.

## Forbidden side effects

V2-004 must not:

- import or execute `pipeline.py` / `production_pipeline.py`;
- write Notion or note;
- create/update Ready records;
- publish content;
- mutate queues or runtime state;
- resume Daily/Fresh/Rolling workflows;
- commit or push repository content at runtime;
- add schedule/push triggers;
- change V1 Production authority.

## Verification

Implementation uses TDD:

1. RED tests for strict parser, one-call boundary, no retry/fallback, workflow safety, and exact ChatOps command.
2. Minimal implementation.
3. Focused V2 tests.
4. Full pytest + repository guards + Production smoke through existing CI.
5. Draft PR only; no merge without explicit MERGE GO.

A live V2-004 provider run is not part of implementation verification and requires a separate explicit trigger decision after merge.
