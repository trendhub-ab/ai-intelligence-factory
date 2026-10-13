# V2-002 Bounded Live Shadow Acquisition — Design Specification

- Status: APPROVED_BY_CONTINUATION
- Date: 2026-10-14
- Base main: `7f2da927b80d2c5e969e4c4f422ae8a2d015b3df`
- Depends on: V2-001 Shadow Selection Vertical Slice
- Production authority: unchanged (V1)

## 1. Core decision

> **V2は実データを読む。V1には触れない。**

V2-002 connects the V2-001 shadow selector to a very small set of real, read-only public sources. It does **not** connect V2 to Daily/Fresh scheduling, Production persistence, article generation, Notion, note, queues, Ready state, Economic State, or publication authority.

The purpose is to prove that V2 can ingest live candidate supply safely and cheaply before any scheduling or Production cutover is discussed.

## 2. Why this is the next slice

V2-001 proved the selection core with injected deterministic providers. The next uncertainty is not article writing; it is whether V2 can consume real changing source data while preserving the isolation contract.

Connecting V2 to Daily now would combine two unknowns — live acquisition and Production scheduling — and would make failures harder to attribute. V2-002 therefore proves live acquisition first.

## 3. Source choice

V2-002 starts with exactly two read-only, no-paid-model sources:

1. **Hacker News official Firebase API**
   - public GET
   - no authentication required
   - top story IDs followed by bounded item GETs
2. **arXiv API**
   - public GET
   - same primary API family already used by V1
   - bounded AI/ML query only

No GitHub GraphQL source is added in V2-002 because it would introduce token/credential and quota concerns before they are necessary. No Product Hunt/vendor source is added because the first goal is live-acquisition isolation, not source parity with V1.

## 4. Reuse decision

V1 already has `fetch_hackernews_top` and `fetch_arxiv_ai_ml`, but they live inside the large `pipeline.py` Production module.

V2 MUST NOT import `pipeline.py` merely to reuse those functions. That would import Production credentials, provider setup, persistence and publication dependencies into the rebuild sidecar.

V2-002 instead implements a thin, independent read-only adapter layer with injected HTTP GET functions for hermetic tests.

Shared low-level URL/candidate normalization remains delegated to the already-isolated V2-001 selection core.

## 5. Architecture

```text
Manual / bounded caller only
        |
        v
V2 Live Acquisition Adapter
  |                  |
  |                  +--> arXiv public GET
  +--> HN public GET
        |
        v
raw candidate mappings
        |
        v
V2-001 run_shadow_selection
  normalize -> dedupe -> cheap screen -> rank
        |
        v
Deep Dive callback (injected, max 1 by V2-001)
        |
        v
structured shadow report

NO Production write
NO scheduler wiring
NO Notion/note/Ready/queue mutation
```

## 6. New V2-002 responsibilities

V2-002 owns only:

- public read-only HTTP acquisition for the two approved sources
- source-specific parsing into the V2-001 raw candidate shape
- per-request timeout bounds
- per-source item bounds
- total candidate bound before selection
- source failure isolation
- manual orchestration into `run_shadow_selection`
- structured acquisition metadata added to the shadow result where useful

V2-002 does not own:

- article generation
- model routing for public writing
- Notion or note writes
- Production queue / ledger
- Ready state
- Economic State
- Publication Gate
- Daily/Fresh/Rolling scheduling
- V1 retirement

## 7. Candidate mapping

### Hacker News

Accepted item requirements:

- `type == "story"`
- non-deleted / non-dead
- usable `title`
- external `url`; if absent, the item is skipped in V2-002 rather than inventing an external identity

Mapped fields:

- `url`
- `title`
- short description assembled only from public item metadata when available
- `published_at` from HN Unix `time`, converted to UTC ISO-8601

The adapter may include score/comment metadata in the description for screening context, but must not fabricate claims about the linked article.

### arXiv

Accepted entry requirements:

- usable entry ID/URL
- usable title

Mapped fields:

- canonical arXiv abstract URL from the Atom entry id
- title
- abstract as `description`
- published timestamp as `published_at`

The adapter is metadata acquisition only. It does not treat an abstract as proof for claims beyond the paper metadata itself.

## 8. Network contract

All network access is GET-only.

Defaults:

- request timeout: 8 seconds maximum per HTTP request
- HN item fetch count: maximum 8
- arXiv result count: maximum 8
- total candidates handed to V2-001: maximum 12

Caller-supplied limits are clamped to safe maxima.

The implementation must not expose POST/PUT/PATCH/DELETE helpers.

The HTTP layer must be injectable so unit tests require no network.

## 9. Failure isolation

Fail closed and isolate by source:

- HN top-list failure -> HN provider failure; arXiv may continue
- one HN item failure -> skip that item, continue within the HN bound
- arXiv HTTP/XML failure -> arXiv provider failure; HN may continue
- malformed payload -> reject/skip, never fabricate
- both sources unavailable -> V2-001 returns no winner / all-providers-failed semantics

No V2-002 failure may stop or mutate V1 Production.

Provider exception messages must not be copied into public/structured reports; category-level failure is sufficient.

## 10. Deep Dive cost contract

V2-002 does not introduce a new model provider.

It passes an injected Deep Dive callable into V2-001. Therefore:

- maximum Deep Dive attempts remains 1/run
- no rank-2 fallback
- model calls can remain zero for fixture/proof runs
- no paid provider call is required merely to prove live acquisition

A future slice may define a real V2 Deep Dive provider after its budget/evidence contract is separately approved.

## 11. Invocation / rollout

V2-002 is callable manually or from tests, but is **not wired into existing Daily/Fresh workflows**.

No new cron, schedule, repository secret, persistent state branch, queue, database, or service is introduced.

A scheduled shadow run is explicitly deferred to a later V2 slice after live acquisition behavior is observed.

## 12. Observability

The returned shadow report must make it possible to inspect:

- V2 mode remains `shadow`
- source/provider status
- source accepted/rejected counts through V2-001
- bounded candidate counts
- Deep Dive attempted 0/1
- V2 winner/no-winner
- optional V1 comparison status
- configured network/candidate bounds

Never include credentials, raw exception text, private Notion content, or private article manuscripts.

## 13. Side-effect boundary

Tests must prove the V2-002 module:

- does not import `pipeline`
- does not import Notion/note/persistence/publication modules
- has no filesystem writes
- exposes no non-GET HTTP method
- does not mutate Production state
- only composes the V2-001 selector through explicit callables

## 14. Acceptance criteria

1. V2-002 is logically independent from `pipeline.py`.
2. HN and arXiv adapters parse representative fixtures deterministically.
3. All requested limits are clamped to safe maxima.
4. HTTP is GET-only and injectable.
5. Partial source failure is isolated.
6. Malformed source payloads do not create candidates.
7. Live candidates feed the existing V2-001 normalize/dedupe/screen path.
8. Deep Dive remains 0 or 1 and does not fall back to rank 2.
9. Both-source failure produces a fail-closed no-winner report.
10. No Production write/import surface is introduced.
11. No workflow/schedule change is made.
12. Existing full pytest and repository guards remain green.
13. At least one bounded real read-only acquisition proof is attempted if the execution environment permits outbound access; inability to reach a public source is reported as an environment/source observation, not papered over.
14. Human-readable proof makes source counts and winner/no-winner inspectable before any future scheduling decision.

## 15. Deferred after V2-002

- wiring V2 shadow execution into Daily/Fresh
- GitHub authenticated/GraphQL acquisition in V2
- official-vendor source parity
- real model-backed V2 Deep Dive provider
- persistence of V2 reports
- adaptive source/candidate budgets
- Production selection authority
- V2 article generation
- Economic State writer
- V1 retirement

## 16. Review gate

The user instructed the project to proceed after V2-001 merged. This specification keeps all previously approved safety boundaries and does not cross into Production scheduling or authority, so implementation may proceed immediately with TDD.

Implementation order:

1. implementation plan
2. RED adapter/contract tests
3. minimal live-acquisition module
4. orchestration tests into V2-001
5. focused verification
6. full pytest
7. repository guards
8. bounded read-only live proof where environment permits
9. merge-readiness review

Main merge remains separately gated by explicit **MERGE GO**.
