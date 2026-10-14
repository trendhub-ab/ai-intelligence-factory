# V2-005A Selection Value Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic, provider-free Selection Value scoring to V2 shadow selection so high-value AI developments outrank metadata-rich but low-decision-value candidates without changing Evidence eligibility or Production authority.

**Architecture:** Keep existing `screen_candidate()` and `screening_score` as the Evidence-readiness/eligibility contract. Add a pure `score_selection_value()` function and enrich screened candidates with a separate `selection_value_score`/`selection_value_reasons`; rank eligible candidates by Selection Value, then existing screening score, then identity. No network/model/provider/delivery code is added.

**Tech Stack:** Python 3.11, pytest, existing `v2_shadow_selection.py` deterministic shadow core.

**Spec:** `docs/superpowers/specs/2026-10-15-v2-005a-selection-value-calibration-design.md`

## Global Constraints

- Existing `screening_score` semantics remain unchanged.
- Default eligibility threshold remains exactly `40`.
- Selection Value is ranking-only and must not become a hard gate.
- Selection Value uses only normalized `title` and `description` text.
- Added network calls = `0`.
- Added model calls = `0`.
- Added hard gates = `0`.
- HN + arXiv acquisition remains unchanged.
- Rank #1 remains the only candidate eligible for Evidence Deep Dive.
- Gemini Evidence model remains exactly `gemini-3.6-flash` downstream.
- Provider Evidence request budget remains at most `1`; retry = `0`; model fallback = `0`; rank fallback = `0`.
- V1 remains Production authority.
- No Notion, note, Ready, delivery, subscriber, economic, publication, or Production mutation may be introduced.
- Selection Value has four dimensions worth exactly `15` points each, maximum `60`.
- If AI relevance is absent, the Selection Value score is `0`; business/change/applied terms alone do not score.
- Each dimension scores at most once regardless of repeated matching terms.
- Matching is case-insensitive and token/phrase-aware; substrings such as `ai` inside `email` must not count as AI relevance.

## Review Focus

1. **Substring false positives:** `email`, `retail`, or similar text must not trigger the `AI` token; add an explicit word-boundary test in Task 1.
2. **Business-only false positives:** pricing/enterprise/launch text without AI relevance must remain score `0`; add a focused test in Task 1.
3. **Keyword repetition inflation:** repeated `AI`, `API`, or `launch` occurrences must not score a dimension more than once; add a focused test in Task 1.
4. **Eligibility drift:** adding Selection Value must not change the existing `screening_score` or threshold behavior; add a regression assertion in Task 2.
5. **Tie determinism:** equal Selection Value candidates must fall back to `screening_score`, then stable identity; add ranking tests in Task 2.

---

### Task 1: Add pure Selection Value scoring

**Files:**
- Modify: `v2_shadow_selection.py`
- Modify: `tests/test_v2_shadow_selection.py`

**Interfaces:**
- Consumes: normalized candidate mappings containing `title` and `description`.
- Produces: `score_selection_value(candidate: Mapping[str, Any]) -> tuple[int, list[str]]`.

- [ ] **Step 1: Write RED tests for the scoring contract**

Add focused tests asserting:

```python
def test_selection_value_scores_four_dimensions_once():
    candidate = {
        "title": "AI agent API launch for enterprise automation",
        "description": "New pricing and deployment support improves business workflow integration.",
    }
    score, reasons = score_selection_value(candidate)
    assert score == 60
    assert reasons == [
        "ai_relevance",
        "decision_value",
        "change_novelty",
        "applied_reader_value",
    ]
```

Also add:

- `test_selection_value_requires_ai_relevance_for_other_dimensions()` → non-AI pricing/enterprise/launch text returns `(0, [])`.
- `test_selection_value_uses_word_boundaries_for_ai_token()` → text such as `email retail launch pricing` returns `(0, [])`.
- `test_selection_value_does_not_inflate_repeated_keywords()` → repeated terms still cap at `60` and exactly four reasons.
- `test_selection_value_is_case_insensitive_and_deterministic()` → repeated calls with mixed-case text return identical output.
- `test_selection_value_applied_research_can_score_high()` → an AI/inference research candidate mentioning cost reduction, release/result improvement, implementation/deployment reaches at least `45`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
pytest tests/test_v2_shadow_selection.py -k "selection_value" -v
```

Expected: FAIL because `score_selection_value` does not exist.

- [ ] **Step 3: Implement the minimal pure scorer**

In `v2_shadow_selection.py`, add:

```python
def score_selection_value(candidate: Mapping[str, Any]) -> tuple[int, list[str]]:
    ...
```

Implementation contract:

- Combine `title` and `description` only.
- Normalize case and whitespace deterministically.
- Use token/phrase-aware matching, not raw substring matching.
- Four fixed dimensions, each exactly `15` points:
  - `ai_relevance`
  - `decision_value`
  - `change_novelty`
  - `applied_reader_value`
- AI relevance terms include a compact explicit set covering at least: `AI`, `artificial intelligence`, `LLM`, `large language model`, `model`, `agent`, `inference`, `robotics`, `multimodal`, `reasoning`, `neural network`.
- Decision terms include at least: `API`, `pricing`, `price`, `cost`, `enterprise`, `security`, `privacy`, `regulation`, `policy`, `deployment`, `availability`.
- Change terms include at least: `launch`, `release`, `released`, `update`, `new`, `introduces`, `introduced`, `acquisition`, `partnership`, `benchmark`, `improves`, `improvement`.
- Applied terms include at least: `workflow`, `productivity`, `coding`, `automation`, `integration`, `tool use`, `implementation`, `business use`, `customer`, `user`, `deploy`, `deployment`.
- First evaluate AI relevance. If absent, return `(0, [])` immediately.
- Add each reason once in the fixed order above; repeated terms never add extra points.

Do not perform I/O, imports of provider/network clients, or model calls.

- [ ] **Step 4: Run scoring tests and verify GREEN**

Run:

```bash
pytest tests/test_v2_shadow_selection.py -k "selection_value" -v
```

Expected: all Selection Value tests PASS.

- [ ] **Step 5: Commit**

```bash
git add v2_shadow_selection.py tests/test_v2_shadow_selection.py
git commit -m "feat: add V2 selection value scoring"
```

---

### Task 2: Integrate Selection Value into deterministic ranking

**Files:**
- Modify: `v2_shadow_selection.py`
- Modify: `tests/test_v2_shadow_selection.py`

**Interfaces:**
- Consumes: `score_selection_value(candidate)` from Task 1.
- Produces: enriched screened candidates with `selection_value_score: int` and `selection_value_reasons: list[str]`; `rank_candidates()` orders by Selection Value, then screening score, then identity.

- [ ] **Step 1: Write RED tests for calibration and tie-breaking**

Add:

- `test_rank_prefers_shorter_high_value_ai_change_over_long_specialist_abstract()`:
  - Candidate A has a long specialist AI/model abstract sufficient for the existing description completeness bonus but no decision/change/applied terms.
  - Candidate B is shorter but contains AI + API/pricing + launch/release + workflow/deployment value.
  - Assert B ranks first even when A's metadata completeness is at least as strong.
- `test_rank_allows_applied_arxiv_research_to_beat_generic_ai_news()`:
  - Applied research contains AI/inference + cost/deployment + improvement + implementation.
  - Generic AI news contains AI + update only.
  - Assert research ranks first; provider identity itself is not used as a Selection Value bonus/penalty.
- `test_rank_equal_selection_value_falls_back_to_screening_score()`.
- Update the existing identity tie-break test so it explicitly uses candidates with equal Selection Value and equal screening score, then asserts identity order.

- [ ] **Step 2: Run ranking tests and verify RED**

Run:

```bash
pytest tests/test_v2_shadow_selection.py -k "rank_" -v
```

Expected: at least the new calibration test FAILS under the old `screening_score`-first ordering.

- [ ] **Step 3: Enrich `screen_candidate()` without changing existing screening semantics**

After calculating the existing `screening_score`, call `score_selection_value(candidate)` and add:

```python
result["selection_value_score"] = selection_value_score
result["selection_value_reasons"] = selection_value_reasons
```

Keep all existing `screening_score`, `screening_reasons`, and `eligible` calculations unchanged.

- [ ] **Step 4: Change `rank_candidates()` ordering only**

Sort by:

```text
-selection_value_score
-screening_score
candidate_identity
```

Do not change deduplication, eligibility, provider acquisition, or Deep Dive behavior.

- [ ] **Step 5: Pin eligibility non-regression**

Extend the deterministic screen test to assert the pre-V2-005A screening score remains exactly the same for its existing fixture, and `eligible` remains `True`.

- [ ] **Step 6: Run focused selection regression tests**

Run:

```bash
pytest tests/test_v2_shadow_selection.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add v2_shadow_selection.py tests/test_v2_shadow_selection.py
git commit -m "feat: rank V2 candidates by selection value"
```

---

### Task 3: Surface safe diagnostics and verify downstream V2 contracts

**Files:**
- Modify: `v2_shadow_selection.py`
- Modify: `tests/test_v2_shadow_selection.py`
- Test only: existing V2-005/V2-004/V2-live suites.

**Interfaces:**
- Consumes: enriched ranked candidates from Task 2.
- Produces: existing `run_shadow_selection()` report plus `selection_value_score` and `selection_value_reasons` in each `screening` item.

- [ ] **Step 1: Write RED report-contract assertion**

Extend `test_shadow_report_contract_is_machine_readable_and_has_no_write_callbacks()` to assert:

```python
screening = report["screening"][0]
assert isinstance(screening["selection_value_score"], int)
assert isinstance(screening["selection_value_reasons"], list)
```

Also assert no mutation-capable function parameters have been added.

- [ ] **Step 2: Run the report test and verify RED**

Run:

```bash
pytest tests/test_v2_shadow_selection.py::test_shadow_report_contract_is_machine_readable_and_has_no_write_callbacks -v
```

Expected: FAIL because the report summary does not yet expose the new fields.

- [ ] **Step 3: Add only the two safe diagnostic fields to `screening_summary`**

Add:

- `selection_value_score`
- `selection_value_reasons`

Do not expose description, prompt text, provider responses, secrets, headers, or new external payload fields.

- [ ] **Step 4: Run focused and V2 regression suites**

Run at minimum:

```bash
pytest tests/test_v2_shadow_selection.py -v
pytest tests/test_v2_live_shadow_acquisition_budget.py -v
pytest tests/test_v2_shadow_deep_dive.py -v
pytest tests/test_v2_005_live_proof.py -v
pytest tests/test_v2_005_evidence_pack.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add v2_shadow_selection.py tests/test_v2_shadow_selection.py
git commit -m "test: expose V2 selection value diagnostics"
```

---

### Task 4: Full verification and Draft PR readiness

**Files:**
- No new Production files expected.
- Update canonical docs only if an existing freshness/fingerprint guard explicitly requires it.

**Interfaces:**
- Consumes: completed Tasks 1–3.
- Produces: verified implementation branch ready for human review; no merge.

- [ ] **Step 1: Run compile/focused verification**

```bash
python -m py_compile v2_shadow_selection.py
pytest tests/test_v2_shadow_selection.py -v
```

Expected: PASS.

- [ ] **Step 2: Run the repository full pytest suite**

```bash
pytest
```

Expected: PASS with zero failures.

- [ ] **Step 3: Run existing repository guards required by the current main branch**

Use the same guard commands/workflows currently required by main. Do not weaken or bypass a failing guard. If a spec fingerprint is required, update only the canonical documentation demanded by that guard and rerun it.

- [ ] **Step 4: Inspect the final diff for forbidden scope expansion**

Confirm the implementation changes are limited to:

- `v2_shadow_selection.py`
- `tests/test_v2_shadow_selection.py`
- this approved design/plan documentation
- a canonical freshness/fingerprint file only if an existing guard requires it

Confirm no Notion/note/Ready/delivery/subscriber/economic/publication/Production-authority code changed.

- [ ] **Step 5: Reconcile with current `main` if it advanced**

Before opening the PR, refetch `main`. If it advanced, inspect the delta and rebase/reconcile without overwriting unrelated work; rerun focused tests affected by the delta.

- [ ] **Step 6: Open a Draft PR only**

PR body must state:

- V2-005A is provider-free Selection Value calibration.
- Added Gemini calls: `0`.
- Added hard gates: `0`.
- Existing Evidence eligibility threshold: unchanged at `40`.
- V1 Production authority: unchanged.
- Rank #1 / one Evidence request / retry 0 / fallback 0: unchanged.
- Exact fresh verification results.

Stop before merge. Merge requires separate explicit `MERGE GO`.
