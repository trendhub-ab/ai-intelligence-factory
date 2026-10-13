# V2-003 Manual Shadow Observation — Design Specification

- Status: AWAITING_USER_REVIEW
- Date: 2026-10-14
- Base main: `14d37baaaaa976aa8774329e98114a804db49e9f`
- Depends on: V2-001 Shadow Selection Vertical Slice, V2-002 Bounded Live Shadow Acquisition
- Production authority: unchanged (V1)

## 1. Core decision

> **V2は観測する。まだ決定しない。V1には触れない。**

V2-003 adds a manual, zero-model observation path around the already-merged V2 live acquisition and selection components. It exists to show what V2 sees and how its deterministic pre-Deep-Dive ranking behaves against live public data, without giving V2 any Production scheduling, persistence, article generation, Ready-state, Notion, note, publication, or Economic-State authority.

The observation output is diagnostic evidence only. It must never be interpreted as a Production decision or as a completed V2 winner.

## 2. Why V2-003 is the next slice

V2-001 proved deterministic normalize/dedupe/screen/rank plus a one-shot Deep Dive contract.

V2-002 proved bounded live acquisition from Hacker News and arXiv without importing V1 `pipeline.py` or adding Production writes.

The next uncertainty is operational: whether the same V2 components behave usefully when executed in the GitHub Actions environment against changing live data. Adding a real Deep Dive provider now would combine source volatility and model/provider behavior in the same proof. Connecting to Daily would combine live acquisition, orchestration, and Production scheduling.

V2-003 therefore observes live source supply first, at zero model cost and zero Production mutation.

## 3. Rejected alternatives

### A. Add a real Deep Dive provider now

Rejected for this slice.

It would add model availability, provider routing, token cost, and evidence-prompt quality as new variables before GitHub Actions live-source behavior has been observed.

### B. Wire V2 into Daily/Fresh now

Rejected for this slice.

It would couple the rebuild to existing Production orchestration too early and make failures harder to attribute. Daily/Fresh remain entirely V1-controlled.

### C. Scheduled V2 cron

Rejected for this slice.

The first observation path is manual `workflow_dispatch` only. Scheduling is deferred until manual runs prove the live-source path useful and stable.

## 4. Architecture

```text
Manual workflow_dispatch only
          |
          v
V2-003 Observation Runner
          |
          v
V2-002 bounded live acquisition
  |                     |
  +--> HN public GET    +--> arXiv public GET
          |
          v
V2-001 normalize -> dedupe -> cheap screen -> rank
          |
          v
Deep Dive budget = 0
          |
          v
NO V2 winner
          |
          +--> pre_deep_dive_leader observation
          +--> source/status/count/ranking metadata
          |
          v
JSON file in runner workspace
          |
          v
GitHub Actions artifact (short retention)

NO Notion write
NO note write
NO Ready mutation
NO Daily/Fresh invocation
NO model provider
NO secrets required
```

## 5. Manual workflow contract

A new workflow may be added:

- `.github/workflows/v2-shadow-observation.yml`
- trigger: `workflow_dispatch` only
- permissions: `contents: read`
- no `schedule`
- no `push` trigger
- no Production reusable-workflow call
- no repository/environment secret requirement
- no Gemini/OpenAI/provider credential in environment
- checkout the exact triggering commit/ref rather than silently switching to a different Production branch
- bounded timeout
- install only the repository's existing locked dependency set
- execute focused safety tests before the live observation step
- upload only the bounded observation JSON artifact

A typed confirmation input should be required, for example `RUN_V2_SHADOW_OBSERVATION`, to make accidental invocation explicit.

The workflow artifact is observational evidence, not durable application state.

## 6. Zero-model contract

V2-003 must perform **zero Deep Dive attempts**.

Current V2-002 always composes V2-001 with `max_deep_dive_attempts=1`. V2-003 therefore requires the smallest backward-compatible extension to the V2-002 call boundary so callers can explicitly set the Deep Dive budget to `0` or `1`.

Recommended interface:

```python
run_bounded_live_shadow(
    ...,
    max_deep_dive_attempts: int = 1,
)
```

Rules:

- default remains `1`, preserving V2-002 behavior
- caller values are clamped to `0` or `1`
- V2-003 always passes `0`
- when `0`, the injected Deep Dive callable must never be invoked
- report must show `deep_dive_attempted_count == 0`
- report must show `actual_calls.deep_dive == 0`
- no model SDK or model credential may be imported or required by V2-003

This extension changes no Production authority and does not modify V1.

## 7. Pre-Deep-Dive leader semantics

Because Deep Dive is intentionally disabled, V2-003 must **not** claim a V2 winner.

`v2_selected_candidate_identity` remains `null` / no winner under the existing fail-closed V2-001 contract.

V2-003 may derive a separate observational field from the deterministic screening list:

```json
{
  "pre_deep_dive_leader": {
    "candidate_identity": "...",
    "provider": "...",
    "screening_score": 55,
    "eligible": true
  }
}
```

Rules:

- leader is the first ranked candidate in the existing V2-001 `screening` output
- if no screened candidate exists, leader is `null`
- it is explicitly named `pre_deep_dive_leader`, never `winner`, `selected`, `ready`, or `recommended`
- it carries only fields already present in the structured screening output
- it does not expose title, manuscript text, credentials, raw exception messages, or private data

This distinction is mandatory to prevent an observational ranking from being misread as a Production selection decision.

## 8. Observation runner responsibilities

A new runner module, expected name `v2_shadow_observation.py`, owns only:

- invoking `run_bounded_live_shadow` with Deep Dive budget 0
- assigning an opaque run ID
- using current UTC time or an injected time in tests
- deriving `pre_deep_dive_leader` from the returned screening list
- adding a small observation metadata block
- serializing the result as JSON for local/workflow inspection
- writing only to an explicitly supplied output path

It does not own:

- source fetching implementation
- candidate normalization/deduplication/scoring/ranking
- model-backed Deep Dive
- V1 comparison acquisition
- Notion/note writes
- queues/ledgers
- Ready state
- article generation
- publication
- Daily/Fresh/Rolling invocation

## 9. Output path and filesystem boundary

V2-003 is the first V2 slice that intentionally writes a file, but only as an ephemeral workflow artifact source.

Default workflow path:

`article_audit/v2_shadow_observation.json`

Rules:

- parent directory may be created in the checked-out runner workspace
- exactly one JSON report is written per workflow run
- no append-only history or repository commit is created
- no state is read back from previous runs
- no cache is required
- no GitHub issue/comment is created automatically
- artifact retention should be short, recommended 7–14 days
- workflow artifacts are diagnostic evidence, not canonical state

Tests must enforce that the runner cannot write outside the explicitly supplied output path through hidden secondary persistence.

## 10. Observation report contract

The report must include enough information to judge source health and ranking behavior without leaking private or volatile internals.

Required top-level/derived evidence:

- `run_id`
- UTC timestamp
- `mode == "shadow"`
- explicit observation mode, e.g. `manual_zero_model`
- source/provider statuses
- acquired / normalized / deduplicated / screened counts
- bounded source/network configuration
- `deep_dive_attempted_count == 0`
- `actual_calls.deep_dive == 0`
- `v2_selected_candidate_identity == null`
- `pre_deep_dive_leader` or `null`
- failure category from the V2-001 fail-closed path

The artifact may retain candidate identities and screening metadata already present in V2-001, because these are public-source URL identities and deterministic scores. It must not add article-body content, private Notion data, note drafts, secrets, raw stack traces, or raw transport error messages.

## 11. Live-source failure semantics

The existing V2-002 source isolation remains authoritative:

- HN may fail while arXiv continues
- arXiv may fail while HN continues
- both may fail, producing a fail-closed no-winner observation
- one failed source must not cause a Production action

The workflow itself should still complete successfully when the V2 runner returns a valid fail-closed observation report for source unavailability. A source outage is an observed system condition, not necessarily an infrastructure failure.

The workflow should fail only for contract/runner failures such as:

- invalid explicit confirmation
- import/runtime error preventing report construction
- report contract violation
- unexpected Deep Dive attempt
- artifact serialization/write failure

This distinction prevents transient public-source outages from creating noisy false alarms while still preserving evidence of the outage in the JSON report.

## 12. Cost and credential contract

V2-003 must require:

- paid model calls: 0
- Gemini calls: 0
- OpenAI calls: 0
- Notion API calls: 0
- note/browser automation: 0
- GitHub authenticated source acquisition: 0
- new secrets: 0

Only bounded public HTTP GETs from V2-002 plus normal GitHub Actions infrastructure are permitted.

## 13. Production isolation contract

V2-003 must not:

- import `pipeline.py`
- invoke `daily.yml`, `daily-one-shot.yml`, `chatops-one-shot.yml`, Fresh, Rolling Re-review, or note workflows
- import or call Notion write surfaces
- import or call note delivery/browser write surfaces
- mutate Content Intelligence, Technology Intelligence, Presentation DB, Decision Brief, queue, ledger, Ready state, or Economic State
- write to Production-owned files or branches
- commit/push from the workflow
- create or update pull requests/issues/comments during observation

V1 remains the sole Production authority.

## 14. Test strategy

Implementation must follow TDD.

### Focused contract tests

Prove:

1. V2-002 default Deep Dive budget remains 1.
2. explicit Deep Dive budget 0 invokes no Deep Dive callable.
3. values below/above range clamp safely to 0/1.
4. V2-003 report never claims a winner when Deep Dive is disabled.
5. `pre_deep_dive_leader` is derived deterministically from the existing screening order.
6. no candidates -> leader null.
7. partial source failure still produces a valid observation report.
8. both-source failure still produces a valid fail-closed observation report.
9. raw provider exception text is not introduced into the observation artifact.
10. fixed source fixtures + fixed clock produce byte-stable JSON where run ID is fixed.

### Boundary tests

AST/text-level tests should reject:

- V1 `pipeline` import
- Notion/note/persistence/publication imports
- model SDK/provider imports
- mutating network methods in the observation runner
- subprocess/`git` mutation
- additional filesystem writes beyond the explicit JSON output operation
- workflow `schedule`, `push`, write permissions, secret references, Production workflow calls

### Repository verification

Before merge readiness:

- focused V2-003 tests
- full pytest
- repository falsification guard
- workflow reference guard
- integration stability guard
- canonical specification freshness handling if Production-surface classification/fingerprint rules require it
- `git diff --check`

## 15. Live proof

After offline tests are green, perform one bounded manual workflow run from the V2-003 branch if GitHub Actions permits `workflow_dispatch` for the branch/workflow.

Proof goals:

- workflow runs with no secrets/model credentials
- HN/arXiv status is recorded truthfully
- Deep Dive attempts are 0
- artifact is produced
- artifact contains no Production mutation evidence

If GitHub cannot dispatch a workflow that does not yet exist on the default branch, do not weaken the design or merge merely to test it. Record that platform limitation and use the strongest available branch/CI proof; the first post-merge manual run then becomes the live workflow proof.

No Daily/Fresh run is part of V2-003 verification.

## 16. Acceptance criteria

1. Manual-only V2 observation workflow exists with `contents: read` and no schedule.
2. Explicit typed confirmation is required.
3. No repository/environment secrets are required.
4. No paid/model provider call can occur.
5. V2-002 supports explicit zero Deep Dive budget without changing its default behavior.
6. V2-003 always uses Deep Dive budget 0.
7. Observation report shows zero Deep Dive attempts/calls.
8. V2 winner remains absent under zero Deep Dive.
9. `pre_deep_dive_leader` is clearly separate from winner semantics.
10. Live HN/arXiv acquisition remains bounded by V2-002 maxima.
11. Partial/both-source failures remain fail-closed and observable.
12. Exactly one ephemeral JSON report is produced for artifact upload.
13. No V1 Production workflow/state/write surface is invoked.
14. Deterministic fixture tests pass.
15. Full repository tests and guards remain green.
16. Merge remains separately gated by explicit `MERGE GO`.

## 17. Deferred after V2-003

- real model-backed V2 Deep Dive provider
- V2 evidence retrieval beyond current source metadata
- scheduled/cron V2 shadow observation
- automatic V1-vs-V2 live comparison acquisition
- persistent observation history/database
- dashboards/alerts
- Daily/Fresh integration
- Production selection authority
- article generation
- Economic State writing
- V1 retirement

The recommended next slice after successful V2-003 observation is V2-004: a separately budgeted, maximum-one-call real Deep Dive provider with evidence sufficiency kept fail-closed.

## 18. Review gate

This document is the architectural design artifact for V2-003.

No implementation, workflow creation, Production-surface change, or PR merge is authorized by this document alone.

After user review/approval of this spec:

1. create the implementation plan via the Superpowers writing-plans workflow
2. present the plan for review
3. after plan approval, execute TDD implementation on this branch
4. keep any PR Draft and unmerged until a separate explicit `MERGE GO`
