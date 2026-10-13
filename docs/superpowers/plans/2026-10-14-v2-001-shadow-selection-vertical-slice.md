# V2-001 Shadow Selection Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only V2 selection sidecar that acquires bounded candidates, normalizes/deduplicates/screens them, Deep Dives at most one candidate, compares the winner with an optional V1 reference, and emits a structured report without Production mutation.

**Architecture:** Add one focused stdlib-first V2 module and one fixture runner. The module receives provider/deep-dive callables by injection, reuses only the existing conservative URL canonicalizer, and never imports `pipeline.py`, Notion, note delivery, article generation, or Production persistence. All Production authority remains V1.

**Tech Stack:** Python 3, stdlib, pytest, existing `candidate_identity.canonicalize_url`.

**Spec:** `docs/superpowers/specs/2026-10-13-v2-001-shadow-selection-vertical-slice-design.md`

## Global Constraints

- Invariant: **V2が選ぶ。V1が書く。**
- V2-001 is shadow-only and has no Production authority.
- Deep Dive attempts are `0` or `1` per run; never automatically fall back to rank 2.
- Screening is deterministic/provider-free and does not require a model call.
- No Notion, note, article-generation, Ready-state, delivery-ledger, queue, or Economic State mutation.
- Do not modify `pipeline.py` unless an adapter becomes strictly necessary; the planned implementation requires no modification.
- Provider failures are isolated and represented in the report.
- Evidence insufficiency is fail-closed: no fabricated winner.
- No new dependency, service, database, queue, schedule, or secret.
- Main merge requires a separate explicit GO.

## Review Focus

- Duplicate URLs that differ only by tracking parameters must collapse to one stable candidate.
- One provider may fail while another succeeds; the surviving candidate path must continue without turning the provider error into a Production failure.
- A top candidate whose Deep Dive is insufficient must produce `v2_no_winner` and must not Deep Dive the second-ranked candidate.
- Missing V1 reference must produce comparison `unavailable`, not a run failure.
- Empty or malformed provider payloads must fail closed with a machine-readable failure category and zero side effects.

---

### Task 1: V2 candidate contract, normalization, dedupe, and cheap screening

**Files:**
- Create: `v2_shadow_selection.py`
- Create: `tests/test_v2_shadow_selection.py`

**Interfaces:**
- Produces: `ShadowConfig`, `normalize_candidate(raw, provider, acquired_at)`, `deduplicate_candidates(candidates)`, `screen_candidate(candidate, now)`, `rank_candidates(candidates, now)`.
- Consumes: `candidate_identity.canonicalize_url(url: str) -> str`.

- [ ] **Step 1: Write failing tests**

Add tests proving:
- normalization emits a stable canonical identity from `primary_url`/`url`, provider id, title, description, source timestamp, acquisition timestamp;
- UTM/ref variants deduplicate deterministically;
- malformed candidates without URL/title are rejected rather than assigned invented identity;
- screening is deterministic and returns `screening_score`, `screening_reasons`, and an explicit `eligible` boolean;
- rank order is stable for equal scores by candidate identity.

- [ ] **Step 2: Run RED verification**

Run: `pytest tests/test_v2_shadow_selection.py -q`
Expected: FAIL during import because `v2_shadow_selection` does not exist.

- [ ] **Step 3: Implement minimal candidate layer**

Create `v2_shadow_selection.py` with:
- `@dataclass(frozen=True) class ShadowConfig` containing exact bounded defaults: `max_candidates_per_provider=10`, `max_deep_dive_attempts=1`, `min_screening_score=40`;
- conservative normalization using existing `canonicalize_url`;
- deterministic dedupe keeping the first normalized candidate for a stable identity;
- provider-free screening based only on source authority, URL/title/description completeness and timestamp presence;
- deterministic ranking by score descending then identity ascending.

Do not add network, provider SDK, persistence, or Production imports.

- [ ] **Step 4: Run GREEN verification**

Run: `pytest tests/test_v2_shadow_selection.py -q`
Expected: all Task 1 tests PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add V2 shadow candidate selection core`

---

### Task 2: Shadow orchestration, one-shot Deep Dive, fail-closed report, and V1 comparison

**Files:**
- Modify: `v2_shadow_selection.py`
- Modify: `tests/test_v2_shadow_selection.py`

**Interfaces:**
- Consumes Task 1 normalized/ranked candidate functions.
- Produces: `run_shadow_selection(*, providers, deep_dive, config, now, run_id, v1_reference=None) -> dict`.

- [ ] **Step 1: Write failing orchestration tests**

Add tests proving:
- provider acquisition is bounded by `max_candidates_per_provider`;
- one provider exception is isolated and recorded while another provider may still produce a winner;
- zero eligible candidates yields no Deep Dive call and `failure_category="insufficient_evidence"`;
- Deep Dive is called at most once for the top-ranked candidate;
- insufficient Deep Dive result does not fall back to rank 2;
- successful Deep Dive emits a V2 winner identity;
- V1 comparison statuses are exactly `same`, `different`, `v2_no_winner`, `unavailable`;
- report includes counts, provider statuses, screening summaries, Deep Dive attempted count, budgets, mode=`shadow`, and actual provider/deep-dive call counts;
- no callback for persistence/writes exists in the public API.

- [ ] **Step 2: Run RED verification**

Run: `pytest tests/test_v2_shadow_selection.py -q`
Expected: new orchestration tests FAIL because `run_shadow_selection` is not implemented.

- [ ] **Step 3: Implement minimal orchestration**

Implement `run_shadow_selection` as a pure orchestration function:
- call each named provider once;
- slice each provider result to `max_candidates_per_provider` before normalization;
- isolate provider exceptions into provider status entries;
- normalize, dedupe, screen, rank;
- if no eligible candidate, return fail-closed report with zero Deep Dive attempts;
- otherwise invoke `deep_dive(top_candidate)` exactly once;
- accept a winner only when the returned mapping has `evidence_sufficient is True`;
- never attempt rank 2 on failure/insufficiency;
- compare to optional V1 identity and emit one of the four specified statuses;
- return only structured data and perform no file/network/database writes itself.

- [ ] **Step 4: Run GREEN verification**

Run: `pytest tests/test_v2_shadow_selection.py -q`
Expected: all Task 1–2 tests PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: orchestrate V2 shadow selection`

---

### Task 3: Bounded provider-free shadow proof and repository regression

**Files:**
- Create: `v2_shadow_selection_fixture.py`
- Create: `tests/test_v2_shadow_selection_fixture.py`
- Modify: PR #777 description after verification only.

**Interfaces:**
- Consumes: `run_shadow_selection`.
- Produces: `build_fixture_report() -> dict` and CLI JSON output for human inspection.

- [ ] **Step 1: Write failing fixture-runner test**

Add a test proving a fixed two-provider fixture:
- includes one tracking-parameter duplicate;
- yields one deterministic V2 winner;
- attempts exactly one Deep Dive;
- reports `comparison_status="different"` against a fixed V1 reference;
- contains no keys named `notion`, `note`, `publish`, `ready_state`, `economic_state`, or `delivery_ledger`.

- [ ] **Step 2: Run RED verification**

Run: `pytest tests/test_v2_shadow_selection_fixture.py -q`
Expected: FAIL because fixture runner does not exist.

- [ ] **Step 3: Implement provider-free fixture runner**

Create `v2_shadow_selection_fixture.py` with `build_fixture_report()` and `if __name__ == "__main__": print(json.dumps(...))`. Use only in-memory fixtures and a deterministic Deep Dive callable; no external API or persistence.

- [ ] **Step 4: Run focused GREEN verification**

Run: `pytest tests/test_v2_shadow_selection.py tests/test_v2_shadow_selection_fixture.py -q`
Expected: PASS.

- [ ] **Step 5: Run full repository verification**

Run: `pytest -q`
Expected: repository suite exits 0 with zero failures.

- [ ] **Step 6: Run repository guards through PR CI**

Use Draft PR #777 CI for the implementation head. Inspect every triggered run/job; no required repository guard may be red before merge readiness is claimed.

- [ ] **Step 7: Capture bounded shadow proof**

Run: `python v2_shadow_selection_fixture.py`
Expected JSON contains `mode="shadow"`, `deep_dive_attempted_count=1`, a stable winner identity, a non-mutating comparison status, and bounded configured/actual call counts.

- [ ] **Step 8: Commit**

Commit message: `test: add bounded V2 shadow proof`

---

## Final review

- Compare branch to base main `8cc13a90272733f7f3cd0b53a008717f2bbe8314`.
- Re-read the design spec and map all 12 acceptance criteria to code/tests/CI evidence.
- Review specifically for accidental imports/calls into Notion, note, article generation, delivery ledger, queues, Ready mutation, or Economic State mutation.
- Review provider exceptions, malformed payloads, duplicate identity, deterministic ranking, one-shot Deep Dive, and V1 comparison semantics.
- Keep PR #777 Draft and do not merge without separate explicit `MERGE GO`.
