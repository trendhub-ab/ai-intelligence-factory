# Saved-X bounded screening validation — 2026-09-11

## Target

- Candidate: Defense Factory
- Canonical primary URL: `https://openai.com/the-defense-factory`
- X discovery provenance: post `2097786616311840853`
- Prepared source fixture: `x_discovery/fixtures/defense_factory_boundary_20260911.json`
- Historical cached primary body was **not** reused; the fixture explicitly records a 2026-09-11 paraphrase of the current official page for boundary validation only.

## Safety contract

The validation entered through `production_pipeline.py` using the existing `x_saved_candidate_validation` mode plus an explicit `AIIF_X_SCREENING_EXECUTE=true` gate.

For each validation process:

- exactly one candidate
- `GEMINI_DAILY_REQUEST_BUDGET=1`
- `GEMINI_SCREENING_RETRY_BUDGET=0`
- exactly one screening model: `gemini-3.5-flash-lite`
- direct `_generate_via_chat` call, deliberately bypassing `_call_screening_pool` / `_call_model_pool` so 503/429/timeout cannot retry or fall back
- authoritative Notion dedup READ only
- no calibration
- no Notion/Factory content write
- no article generation
- no publication
- no source fetch
- no Apify
- no FetchLayer
- X remains discovery-only evidence provenance

Persistent Gemini quota reservation remained enabled and wrote only quota-accounting state to the existing runtime counter.

## Real result

The first authorized run completed successfully:

- Notion existing URLs read: 1,144
- dedup verified: true
- provider response: HTTP 200
- model: `gemini-3.5-flash-lite`
- Gemini attempts in that process: 1
- prompt tokens: 693
- output tokens: 119
- total tokens: 812
- Decision screening score: 88
- Commercial score: 90
- Shelf-life score: 75
- Topic: SECURITY
- Tracking eligible: true
- status: `SCREENING_VALIDATED`
- Factory content writes: 0
- generation/publication: 0

A second CI path was unintentionally armed while working around the unavailable workflow-dispatch action. Because both queued runs used the same serialized Gemini concurrency group, the second process ran after the first and also made one successful request before the temporary CI job could be removed. This means the **overall engineering operation consumed two Gemini screening requests, not one**, even though each process correctly enforced its local one-request ceiling.

Second result:

- provider response: HTTP 200
- Gemini attempts in that process: 1
- prompt tokens: 693
- output tokens: 112
- total tokens: 805
- Decision screening score: 88
- Commercial score: 90
- Shelf-life score: 80
- Topic: SECURITY
- Tracking eligible: true
- status: `SCREENING_VALIDATED`

The duplicate execution did not create Factory/Notion content, did not fetch sources, and did not generate or publish an article. The temporary live screening CI job and standalone live-trigger workflow were removed immediately after the proof. Normal bounded CI is provider-free again.

## Interpretation

The X-discovered candidate can now be proven through:

`X provenance -> resolved primary URL -> saved/prepared primary text -> production entrypoint -> authoritative Notion dedup -> installed Factory screening prompt -> Gemini screening parser`

The two independent outputs agree on the main decision signal (`score=88`, `commercial=90`, `topic=SECURITY`, `tracking=true`), while shelf-life varied 75 -> 80. This is acceptable model variance and is a useful reason not to treat a single raw screening number as deterministic ground truth.

## Next gate

Do not run another live screening merely to repeat this proof. The next engineering step should be provider-free: connect the parsed screening result to a dry-run post-screening handoff that proves threshold/calibration/deep-dive routing decisions without persistence. Any later Gemini call must receive a new explicit total-operation request ceiling rather than relying only on per-process limits.
