# V2-005D Selection + Evidence Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair cross-source Selection Value distortion and Evidence prompt contamination in the V2 shadow path without adding provider/network calls or changing Production authority.

**Architecture:** Keep existing acquisition adapters, `screening_score`, eligibility, ranking order, and one-shot Evidence budget. Tighten Selection Value so title text must establish AI relevance before descriptions can contribute other value dimensions, extend branded AI vocabulary, and restrict Gemini Evidence prompt metadata to source/provenance fields only.

**Tech Stack:** Python 3.11, pytest, existing V2 shadow selector and Gemini Evidence adapter.

**Spec:** `docs/superpowers/specs/2026-10-16-v2-005d-selection-evidence-integrity-design.md`

## Global Constraints

- Base main: `7cb242d4609fc9a374f96858636734dc4d92c214`.
- V1 remains sole Production authority.
- `screening_score` semantics remain unchanged.
- `DEFAULT_MIN_SCREENING_SCORE` remains `40`.
- Selection Value remains ranking-only, max `60`, four dimensions worth `15` each.
- Rank #1 remains the only Evidence candidate.
- Gemini remains `gemini-3.6-flash` for this shadow Evidence path.
- Evidence request budget <= 1; retry 0; model fallback 0; rank fallback 0.
- Added GET/network calls = 0.
- Added model calls = 0.
- Added hard gates = 0.
- Production mutations = 0.
- Do not trigger another Live Proof under the completed five-run V2-005 protocol.

## Review Focus

1. **Description-manufactured AI relevance:** an opaque version title must stay Selection Value 0 even when its body is AI-rich.
2. **Brand false negatives:** GPT/ChatGPT/Claude/Gemini titles must establish AI relevance without treating bare `model` or unrelated substrings as AI.
3. **Applied research regression:** an AI-relevant research title must still be able to gain decision/change/applied value from its abstract.
4. **Ranking regression:** Selection Value remains first, then unchanged screening score, then stable identity.
5. **Evidence leakage:** internal screening/selection/rank metadata must never enter the Gemini Evidence prompt.

---

### Task 1: Pin cross-source Selection Value defect with RED tests

**Files:**
- Modify: `tests/test_v2_shadow_selection.py`
- Later modify: `v2_shadow_selection.py`

**Interfaces:**
- Consumes: `score_selection_value(candidate)`, `normalize_candidate(...)`, `rank_candidates(...)`.
- Produces: regression tests for title-grounded AI relevance, branded AI recognition, applied-research preservation, and live-proof-shaped ranking.

- [ ] **Step 1: Add failing test `test_selection_value_requires_ai_relevance_in_title_not_description()`**

Use title `v3.28.0` and an AI-rich release description. Assert `(0, [])`.

- [ ] **Step 2: Add failing branded-title tests**

Parametrize `GPT-6 for everyone`, `ChatGPT Work update`, `Introducing Claude Opus 5`, and `Gemini API availability`. Assert each includes `ai_relevance` and has positive score.

- [ ] **Step 3: Add failing rank regression**

Construct:
- OfficialVendor: `GPT-6 for everyone`, empty description, no timestamp.
- GitHub: `v3.28.0`, substantive recent description containing agent/API/release/deployment/workflow terms.

Assert OfficialVendor ranks first despite the GitHub candidate having the higher `screening_score`.

- [ ] **Step 4: Pin applied-research preservation**

Use an AI-relevant title and description-only decision/applied terms. Assert score >= 45 and relevant reasons remain.

- [ ] **Step 5: Run focused RED**

Run:

```bash
pytest tests/test_v2_shadow_selection.py -k "title_not_description or branded or official_model_announcement or applied_research" -v
```

Expected: new title-grounding / brand / ranking tests fail on current implementation for the intended reason.

---

### Task 2: Implement minimal Selection Value correction

**Files:**
- Modify: `v2_shadow_selection.py`
- Test: `tests/test_v2_shadow_selection.py`

**Interfaces:**
- `score_selection_value(candidate: Mapping[str, Any]) -> tuple[int, list[str]]`

- [ ] **Step 1: Split normalized selection text into title tokens and combined title+description tokens**

Keep token/phrase-aware deterministic matching.

- [ ] **Step 2: Require AI relevance on title tokens**

If title lacks AI relevance, return `(0, [])` before evaluating other dimensions.

- [ ] **Step 3: Extend AI terms**

Add exact terms: `gpt`, `chatgpt`, `claude`, `gemini`.

- [ ] **Step 4: Extend novelty morphology**

Add `introducing`, `announcing`, `launched`, `launches` while preserving one-score-per-dimension behavior.

- [ ] **Step 5: Run full selection file**

```bash
pytest tests/test_v2_shadow_selection.py -v
```

Expected: PASS and existing screening/eligibility assertions unchanged.

---

### Task 3: Pin Evidence prompt contamination with RED test

**Files:**
- Modify: `tests/test_v2_shadow_deep_dive.py`
- Later modify: `v2_shadow_observation.py`

**Interfaces:**
- Consumes: `build_deep_dive_prompt(candidate)`.
- Produces: exact prompt-field boundary regression.

- [ ] **Step 1: Import `build_deep_dive_prompt`**

- [ ] **Step 2: Add failing `test_deep_dive_prompt_excludes_internal_selection_and_screening_metadata()`**

Build a candidate containing source fields plus screening/selection fields. Assert prompt excludes:

- `screening_score`
- `screening_reasons`
- `selection_value_score`
- `selection_value_reasons`

Assert source fields `provider`, `primary_url`, `title`, `description`, `source_timestamp` remain represented.

- [ ] **Step 3: Run RED**

```bash
pytest tests/test_v2_shadow_deep_dive.py::test_deep_dive_prompt_excludes_internal_selection_and_screening_metadata -v
```

Expected: FAIL because current prompt includes screening fields.

---

### Task 4: Restrict Evidence prompt to source/provenance metadata

**Files:**
- Modify: `v2_shadow_observation.py`
- Test: `tests/test_v2_shadow_deep_dive.py`

**Interfaces:**
- `build_deep_dive_prompt(candidate: Mapping[str, Any]) -> str`

- [ ] **Step 1: Remove internal fields from prompt payload**

Keep exactly: `provider`, `primary_url`, `title`, `description`, `source_timestamp`.

- [ ] **Step 2: Tighten prompt instruction**

State that `evidence_points` must be factual source-grounded points and must not cite AIIF internal score/rank/pipeline metadata.

- [ ] **Step 3: Run deep-dive tests**

```bash
pytest tests/test_v2_shadow_deep_dive.py -v
```

Expected: PASS; one-request/no-retry behavior unchanged.

---

### Task 5: Verify V2 safety and repository-wide regression

**Files:**
- No functional expansion.
- Update canonical fingerprint only if repository guard reports it stale.

- [ ] **Step 1: Run focused V2 suites**

```bash
pytest tests/test_v2_shadow_selection.py tests/test_v2_shadow_deep_dive.py tests/test_v2_005_live_proof.py tests/test_v2_005_evidence_pack.py tests/test_v2_four_source_live.py -v
```

- [ ] **Step 2: Run full pytest**

```bash
pytest
```

- [ ] **Step 3: Run repository guards**

Run the same falsification/specification/P0-B guards required by recent V2 PRs.

- [ ] **Step 4: If fingerprint is stale, update only the canonical fingerprint through the repository's existing deterministic fingerprint procedure and rerun guards**

- [ ] **Step 5: Confirm no live Gemini call and no Production mutation occurred**

- [ ] **Step 6: Prepare Draft PR for human review; do not merge without explicit MERGE GO**
