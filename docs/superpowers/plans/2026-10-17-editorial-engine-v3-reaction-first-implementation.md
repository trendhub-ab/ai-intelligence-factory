# Editorial Engine v3 Reaction-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the experimental C Editorial Engine with the approved Reaction-First five-stage contract while preserving one logical Gemini call per case, frozen A/B comparators, and all Production boundaries.

**Architecture:** Keep the Phase 0 experiment isolated. C emits five explicit stage artifacts in one JSON object: Writer Reaction → Editorial Discovery → Cognitive Shift → Persona Article Generation → Fact-Safe Review. `live.py` validates every stage fail-closed and uses Fact-Safe Review as final C output; A/B, evidence inputs, provider locking, checkpointing, C-only replay, and Production paths remain unchanged.

**Tech Stack:** Python 3.11, pytest, GitHub Actions, google-genai only in manually dispatched live proof.

**Spec:** `docs/superpowers/specs/2026-10-17-editorial-engine-v3-reaction-first-design.md`

## Global Constraints

- Production Writer, Fresh, Daily, Notion, note delivery, Evidence collection, Fact Gate, and Publication Gate remain untouched.
- C remains exactly one logical provider call per case; C-only remains exactly 3 logical calls for the three frozen cases.
- A/B comparator text and immutable case inputs remain reusable from the expected checkpoint.
- Lite models remain forbidden; run-level model locking remains unchanged.
- Normal push runs focused contract tests only; Gemini live generation remains `workflow_dispatch` + `run_live=true` only.
- All five C stage outputs and the final article must be non-empty or fail closed.
- Human Persona/interest judgment remains the final GO gate; automated structure tests cannot mark Phase 0 GO.

## Review Focus

- Missing or blank Reaction-First stage must fail closed rather than silently falling back to another stage.
- Fact-Safe Review must be the only final C article source while preserving every intermediate stage for diagnostics.
- The prompt must require evidence-specific Reaction/Curiosity/Question/Future Imagination and theme-specific Cognitive Shift, not generic enthusiasm or a fixed emotional curve.
- Review instructions must default to preserving the Persona Article unchanged and permit only the smallest local correction for a concrete defect.
- C-only replay must preserve A/B and still spend exactly three logical C calls.

---

### Task 1: Reaction-First stage contract and prompts

**Files:**
- Modify: `tests/test_editorial_engine_v3_phase0.py`
- Modify: `experiments/editorial_engine_v3_phase0/contract.py`
- Modify: `experiments/editorial_engine_v3_phase0/prompts.py`

**Interfaces:**
- Consumes: existing `Phase0Case`, frozen `READY_CASES`, current evidence boundary helper, Persona policy.
- Produces: `EDITORIAL_STAGES == ("Writer Reaction", "Editorial Discovery", "Cognitive Shift", "Persona Article Generation", "Fact-Safe Review")`; `build_editorial_stage_prompts(case)` and `build_editorial_bundle_prompt(case)` matching those keys.

- [ ] **Step 1: Write the failing contract/prompt tests**

Update/add tests asserting:
- `EDITORIAL_STAGES` is the five approved Reaction-First stages in order.
- Writer Reaction prompt contains `Reaction`, `Curiosity`, `Question`, `Future Imagination`, and bounded `Emotion Intensity` guidance.
- Editorial Discovery contains `Surface`, `Interesting Tension`, `Evidence Pivot`, `Deeper Insight`, `Editorial Thesis`.
- Cognitive Shift contains `Before View`, `Evidence Encounter`, `After View`, `What I Now Find Interesting` and rejects a fixed emotional curve in its instructions.
- Persona Article Generation explicitly preserves writer-owned reaction/question/cognitive movement/discovery and still targets adult business readers.
- Fact-Safe Review says unchanged-by-default / smallest local edit and forbids flattening first person, curiosity, specific questions, or supported future imagination.
- Bundle prompt requests exactly the five keys and keeps the no-external-Fact rule.

- [ ] **Step 2: Run focused test and verify RED**

Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0.py`
Expected: FAIL because current code still exposes Editorial Discovery / Persona Narrative / Article Writing / Editorial Review.

- [ ] **Step 3: Implement the minimal contract and prompt change**

In `contract.py`, replace only the C `EDITORIAL_STAGES` constant; keep A/B contracts unchanged.

In `prompts.py`, keep the shared evidence boundary and Persona policy, but replace C stage prompts/bundle with the five approved contracts. Preserve one bundled provider generation; do not add provider calls or Production imports.

- [ ] **Step 4: Re-run focused test and verify GREEN**

Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(phase0): add reaction-first editorial stage contracts`

### Task 2: Fail-closed live parsing and C-only compatibility

**Files:**
- Modify: `tests/test_editorial_engine_v3_phase0_live.py`
- Modify: `experiments/editorial_engine_v3_phase0/live.py`

**Interfaces:**
- Consumes: Task 1 `EDITORIAL_STAGES` and bundle keys.
- Produces: `_parse_editorial_bundle(text) -> tuple[str, dict[str, str]]` where final is `Fact-Safe Review`; `_editorial_article` and C-only replay remain one call per case.

- [ ] **Step 1: Write failing live tests**

Update/add tests asserting:
- a five-key bundle parses in exact `EDITORIAL_STAGES` order;
- final article is `Fact-Safe Review`;
- parametrized missing-stage coverage fails closed for all five stages;
- C-only replay fake provider returns all five keys, preserves A/B, records all five diagnostic outputs, and still makes exactly 3 calls.

- [ ] **Step 2: Run live-focused tests and verify RED**

Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0_live.py`
Expected: FAIL because parser/fake bundle still use `Editorial Review` and old four-stage payloads.

- [ ] **Step 3: Implement minimal live parser change**

Change `_parse_editorial_bundle` to validate every stage in `EDITORIAL_STAGES` and return `stages["Fact-Safe Review"]` as final. Do not alter retry/fallback/model-lock/call-budget/checkpoint semantics.

- [ ] **Step 4: Re-run live-focused tests and verify GREEN**

Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0_live.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(phase0): parse reaction-first editorial bundles`

### Task 3: Regression and live-generation guard

**Files:**
- Verify only: `.github/workflows/editorial-engine-v3-phase0.yml`
- Verify only: focused Phase 0 suite and repository test suite.

**Interfaces:**
- Consumes: Tasks 1-2 complete branch.
- Produces: evidence that push is provider-free, Phase 0 resilience remains green, and no Production surface changed.

- [ ] **Step 1: Run complete focused Phase 0 suite**

Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0.py tests/test_editorial_engine_v3_phase0_live.py`
Expected: PASS.

- [ ] **Step 2: Verify workflow live gate**

Assert `.github/workflows/editorial-engine-v3-phase0.yml` keeps `live-proof` guarded by `github.event_name == 'workflow_dispatch' && inputs.run_live == true`; push may run contract tests but cannot call Gemini.

- [ ] **Step 3: Run repository regression suite**

Run: `python -m pytest -q`
Expected: PASS; any unrelated pre-existing failures must be reported by name and not hidden.

- [ ] **Step 4: Verify scope**

Compare branch to the Task 1 base and confirm implementation changes are limited to Phase 0 tests plus `contract.py`, `prompts.py`, `live.py`, and this plan/spec documentation. No Production files changed by this implementation.

- [ ] **Step 5: Hold live proof**

Do **not** dispatch Gemini yet. Phase 0 remains NO-GO until the owner authorizes the planned C-only 3-call live proof after implementation/regression is green.

## Self-review

- Spec coverage: all five stage contracts, adaptive emotion guidance, one-call bundling, diagnostic artifacts, fail-closed parsing, C-only budget, push/live isolation, and Human GO gate are covered.
- Type consistency: `EDITORIAL_STAGES` is the single ordered source used by prompts, parser, and tests; final C article is explicitly `Fact-Safe Review`.
- Proportion: implementation is intentionally limited to the experimental surface and avoids redesigning provider/retry/checkpoint infrastructure.
