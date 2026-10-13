# V2-002 Bounded Live Shadow Acquisition — Implementation Plan

**Goal:** Connect V2-001 shadow selection to bounded real read-only Hacker News and arXiv candidate acquisition without importing V1 `pipeline.py`, changing workflows, or granting V2 Production authority.

**Base:** `7f2da927b80d2c5e969e4c4f422ae8a2d015b3df`

**Design:** `docs/superpowers/specs/2026-10-14-v2-002-bounded-live-shadow-acquisition-design.md`

**Invariant:** V2 reads live data; V1 remains untouched.

---

## Task 1 — Lock the read-only adapter contract with RED tests

**Create:**
- `tests/test_v2_live_shadow_acquisition.py`

Write tests before implementation for:

- bounded/clamped configuration
- Hacker News top-story + item mapping
- HN deleted/dead/non-story/no-external-URL rejection
- single HN item request failure isolation
- arXiv Atom mapping
- malformed arXiv XML fail-closed
- source-level HTTP failure classification
- GET-only injected HTTP callable contract

Expected RED: import failure because `v2_live_shadow_acquisition` does not yet exist.

## Task 2 — Implement the smallest source adapters

**Create:**
- `v2_live_shadow_acquisition.py`

Implementation constraints:

- stdlib + `requests` + `v2_shadow_selection`
- never import `pipeline.py`
- no Notion/note/persistence/publication imports
- no filesystem writes
- no HTTP mutation verbs
- Hacker News official `v0/topstories` + `v0/item/<id>` GET only
- arXiv `https://export.arxiv.org/api/query` GET only
- arXiv query parity with current V1: `cat:cs.AI OR cat:cs.LG`, newest first
- max HN items 8
- max arXiv items 8
- max combined candidates 12
- timeout max 8s

Run focused tests and get GREEN.

## Task 3 — Prove composition with V2-001

Extend `tests/test_v2_live_shadow_acquisition.py` with RED tests for a manual orchestration function that:

- constructs provider callables from the two adapters
- feeds them into `run_shadow_selection`
- passes an injected Deep Dive callable
- preserves Deep Dive maximum 1
- supports optional read-only V1 reference
- reports network/candidate bounds
- isolates one source failure while the other source can still win
- both-source failure returns no winner
- applies total candidate bound before V2-001

Implement only enough orchestration to make those tests GREEN.

## Task 4 — Lock side-effect isolation

**Create:**
- `tests/test_v2_live_shadow_acquisition_boundary.py`

AST/source-contract tests must prove:

- no `pipeline` import
- no Notion/note/persistence/publication imports
- no filesystem-writing calls
- no `post`, `put`, `patch`, `delete` network methods
- no workflow/scheduler integration

If the new root Python module triggers the existing member/customer surface classification contract, register it explicitly as non-member infrastructure; do not relax the guard.

If canonical Production fingerprint freshness changes, synchronize the canonical specification metadata using the existing guard output; do not weaken the guard.

## Task 5 — Bounded proof asset

**Create:**
- `tests/v2_live_shadow_acquisition_fixture.py`
- `tests/test_v2_live_shadow_acquisition_fixture.py`

Build a deterministic injected-HTTP fixture proving:

- both source formats are consumed
- total limits are enforced
- source failures are isolated
- candidate data flows through V2-001
- Deep Dive remains exactly 0/1
- repeat runs with fixed time and fixture input produce identical reports
- no Production mutation surface exists

Then attempt one real read-only acquisition proof if a safe execution environment with outbound access is available. Use no secrets and no paid model call. A network block is an observation, not a reason to bypass isolation.

## Task 6 — Repository verification

Open/maintain a Draft PR for CI observation.

Required final evidence on the exact final head:

1. focused V2-002 tests GREEN
2. full repository pytest GREEN
3. repository-wide falsification guard GREEN
4. integration stability/hermeticity GREEN
5. workflow reference guard GREEN
6. Notion access policy guard GREEN
7. synthetic Production smoke GREEN
8. `pipeline.py` unchanged
9. `.github/workflows/*` unchanged
10. branch not behind main

## Task 7 — Merge readiness only

Update the Draft PR with:

- architecture boundary
- TDD RED/GREEN evidence
- exact test counts
- bounded proof result
- live acquisition observation if obtained
- changed-file inventory

Do **not** merge. Main integration requires a separate explicit **MERGE GO** from the user.
