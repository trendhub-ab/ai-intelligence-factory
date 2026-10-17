# V2 Semantic Gold Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, provider-free Gold-label benchmark that measures V2 Semantic Screening with per-dimension Precision / Recall / F1, macro metrics, exact-match accuracy, and all-positive saturation rate.

**Architecture:** Keep the benchmark entirely separate from the Gemini provider. A versioned JSON Gold dataset is loaded and strictly validated by a new offline evaluator; predictions are supplied externally using the same four-boolean contract as Semantic Screening. CI exercises only schema validation and deterministic fixtures, while future manual provider-backed predictions can be scored by the same evaluator without granting mutation authority.

**Tech Stack:** Python 3.11 stdlib (`json`, `pathlib`, `argparse`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-17-v2-source-acquisition-reliability-gold-benchmark-design.md`

## Global Constraints

- CI must make zero Gemini/provider calls.
- Gold labels must never be generated, changed, or auto-approved from model output.
- Dataset records use only `case_id`, source text/context, four Gold booleans, rationale, and provenance/version metadata.
- Prediction contract must contain exactly the same case IDs and four boolean fields.
- Zero denominator for Precision/Recall/F1 is `0.0`, never NaN.
- Do not claim statistically representative real-world accuracy from the initial seed dataset.
- No Production writes, Notion/note/Ready/publication changes, or model-routing changes.

## Review Focus

- Boolean values must reject integers `0/1`; Task 1 pins strict `type(value) is bool` validation.
- Duplicate Gold case IDs must fail even when records are otherwise identical; Task 1 pins this.
- Predictions with one extra or one missing case must fail closed; Task 2 pins this.
- A dimension with no predicted positives or no Gold positives must return deterministic `0.0` metrics; Task 2 pins this.
- CLI/report output must not silently convert contract errors into misleading zero scores; Task 4 pins non-zero exit/failure behavior.

---

### Task 1: Gold dataset contract and strict loader

**Files:**
- Create: `v2_semantic_gold_benchmark.py`
- Create: `tests/test_v2_semantic_gold_benchmark.py`
- Create later in Task 3: `benchmarks/v2_semantic_gold_v1.json`

**Interfaces:**
- Produces: `SEMANTIC_FIELDS = ("ai_relevant", "decision_value", "change_novelty", "applied_reader_value")`.
- Produces: `GoldBenchmarkContractError(ValueError)`.
- Produces: `validate_gold_dataset(payload: Any) -> list[dict[str, Any]]`.
- Produces: `load_gold_dataset(path: str | Path) -> list[dict[str, Any]]`.
- Dataset top-level contract: `{"benchmark_version": "v1", "label_contract": "v2_semantic_screening", "cases": [...]}`.

- [ ] **Step 1: Write RED schema tests**

Assert acceptance of one valid record and rejection of missing/extra keys, duplicate/blank `case_id`, non-string title/description/rationale, unsupported `benchmark_version`, and non-boolean Gold fields including `0`/`1`.

A case record must contain exactly:

```text
case_id
title
description
source_family
gold
rationale
label_provenance
```

`gold` must contain exactly the four semantic fields.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_v2_semantic_gold_benchmark.py`

Expected: FAIL because evaluator module does not exist.

- [ ] **Step 3: Implement only the loader/validator**

Do not import `requests`, Gemini code, provider routing, V1 pipeline, Notion, or publication modules.

- [ ] **Step 4: Run focused tests GREEN**

Run: `python -m pytest -q tests/test_v2_semantic_gold_benchmark.py`

Expected: loader tests PASS.

- [ ] **Step 5: Commit**

```bash
git add v2_semantic_gold_benchmark.py tests/test_v2_semantic_gold_benchmark.py
git commit -m "feat: define V2 semantic gold dataset contract"
```

### Task 2: Deterministic metric evaluator

**Files:**
- Modify: `v2_semantic_gold_benchmark.py`
- Modify: `tests/test_v2_semantic_gold_benchmark.py`

**Interfaces:**
- Produces: `validate_predictions(predictions: Any, *, case_ids: Sequence[str]) -> dict[str, dict[str, bool]]`.
- Produces: `evaluate_predictions(gold_cases: Sequence[Mapping[str, Any]], predictions: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]`.
- Returned report contains: `sample_count`, `dimensions`, `macro`, `exact_match_accuracy`, `all_positive_saturation_rate`.
- Each dimension contains: `tp`, `fp`, `tn`, `fn`, `precision`, `recall`, `f1`.

- [ ] **Step 1: Write RED confusion-matrix fixture**

Use a small hand-computable fixture with both positives and negatives and assert exact TP/FP/TN/FN for all four fields.

- [ ] **Step 2: Write RED metric-boundary tests**

Assert:

```python
assert no_predicted_positives["precision"] == 0.0
assert no_gold_positives["recall"] == 0.0
assert empty_harmonic_case["f1"] == 0.0
```

Also assert macro metrics are arithmetic means over exactly four dimensions, exact-match accuracy counts all-four matches, and saturation rate counts rows predicted all-true.

- [ ] **Step 3: Write RED prediction-contract tests**

Reject missing/extra case IDs, duplicate identities in list-shaped input if supported, missing/extra fields, and non-booleans. Keep accepted canonical prediction shape as mapping keyed by `case_id`.

- [ ] **Step 4: Run RED**

Run: `python -m pytest -q tests/test_v2_semantic_gold_benchmark.py`

Expected: evaluator tests FAIL.

- [ ] **Step 5: Implement metrics minimally**

Round only for presentation if needed; keep underlying arithmetic deterministic floats. Do not add thresholds that convert the benchmark into a release gate in this task.

- [ ] **Step 6: Run GREEN**

Run: `python -m pytest -q tests/test_v2_semantic_gold_benchmark.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add v2_semantic_gold_benchmark.py tests/test_v2_semantic_gold_benchmark.py
git commit -m "feat: add V2 semantic precision recall evaluator"
```

### Task 3: Versioned seed Gold dataset

**Files:**
- Create: `benchmarks/v2_semantic_gold_v1.json`
- Modify: `tests/test_v2_semantic_gold_benchmark.py`

**Interfaces:**
- Consumes: Task 1 loader.
- Produces: a reviewed regression corpus; it is not a statistically representative population estimate.

- [ ] **Step 1: Assemble a mixed seed set**

Use at least 16 cases with balanced boundary coverage, including:

- clear non-AI negatives such as the Tesla Roadster-style case;
- AI-adjacent but low-information HN metadata;
- concrete AI SDK/API/model releases;
- safety/policy/education items where only a subset of dimensions is true;
- implementation/workflow cases;
- ambiguous cases whose conservative default is false.

Prefer actual safe titles/descriptions already present in V2 Run #38982633659 / #38993885684 artifacts plus explicit calibration fixtures. Do not include secrets, raw provider bodies, internal scores, or private data.

- [ ] **Step 2: Label from the approved semantic contract**

For every case, supply four Gold booleans and a concise rationale that points only to title/description evidence. `label_provenance` must identify the approved contract/version, not a model name.

- [ ] **Step 3: Add dataset integrity tests**

Load the committed file and assert version `v1`, unique cases, minimum 16 cases, at least one true and one false for each dimension, at least one all-false case, and at least one mixed-vector case. This prevents a useless saturated Gold set.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest -q tests/test_v2_semantic_gold_benchmark.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add benchmarks/v2_semantic_gold_v1.json tests/test_v2_semantic_gold_benchmark.py
git commit -m "test: add V2 semantic gold regression corpus"
```

### Task 4: Offline CLI/report path

**Files:**
- Modify: `v2_semantic_gold_benchmark.py`
- Modify: `tests/test_v2_semantic_gold_benchmark.py`
- Create: `tests/fixtures/v2_semantic_predictions_fixture.json`

**Interfaces:**
- Produces CLI: `python v2_semantic_gold_benchmark.py --gold <path> --predictions <path> [--output <path>]`.
- Predictions file top level: `{"predictions": {"case-id": {four booleans}}}`.
- stdout or output JSON contains only benchmark metadata/metrics, never model prompts or credentials.

- [ ] **Step 1: Write RED CLI tests**

Test a deterministic fixture produces the expected report, malformed predictions exit non-zero, and `--output` writes only the requested UTF-8 JSON file.

- [ ] **Step 2: Implement CLI as a thin wrapper**

CLI calls the same Task 1/2 loader/evaluator. It must not import or instantiate `GeminiSemanticScreeningProvider` and must not read environment secrets.

- [ ] **Step 3: Prove provider-free boundary**

Add source/AST assertions that the benchmark module has no `requests`, `google`, `GEMINI_API_KEY`, `v2_semantic_screening.GeminiSemanticScreeningProvider`, Production persistence, Notion, note, or publication imports.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest -q tests/test_v2_semantic_gold_benchmark.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add v2_semantic_gold_benchmark.py tests/test_v2_semantic_gold_benchmark.py tests/fixtures/v2_semantic_predictions_fixture.json
git commit -m "feat: add offline V2 semantic benchmark runner"
```

### Task 5: CI-safe regression integration and final verification

**Files:**
- Modify: `.github/workflows/v2-shadow-deep-dive.yml` only to include `tests/test_v2_semantic_gold_benchmark.py` in the existing provider-free safety step.
- Modify: `tests/test_v2_shadow_deep_dive_workflow.py`.
- Modify: `AI_Intelligence_Factory_最終仕様書.md` only if canonical guard/fingerprint synchronization is required by changed monitored surfaces.

**Interfaces:**
- No new workflow, secret, provider call, schedule, permission, or merge gate.
- Gold benchmark test executes before the live provider-backed observation as ordinary pytest only.

- [ ] **Step 1: Add RED workflow contract assertion**

Require the benchmark test file in the reviewed safety-suite list and assert no CLI provider invocation is added to the workflow.

- [ ] **Step 2: Update workflow test list only**

Do not add a provider-backed benchmark run to CI.

- [ ] **Step 3: Run focused regression**

Run: `python -m pytest -q tests/test_v2_semantic_gold_benchmark.py tests/test_v2_semantic_screening.py tests/test_v2_variable_gemini_fallback.py tests/test_v2_shadow_deep_dive_workflow.py`

Expected: PASS.

- [ ] **Step 4: Run full repository verification on the exact final head**

Run `python -m pytest -q`, Repository-wide Falsification Guard, P0-B Offline Verification, Notion Access Policy Guard, Workflow Reference Guard, and Synthetic Production smoke. Confirm Production write isolation remains true and Gemini request ceilings remain unchanged.

- [ ] **Step 5: Record baseline metrics honestly**

Run the offline CLI against the fixed synthetic prediction fixture only and record those deterministic metrics in the PR. Do not call them live model accuracy. A future manual provider-backed prediction file may be evaluated separately after merge.

- [ ] **Step 6: Stop at merge-ready**

Update/open Draft PR with dataset inventory, metric-contract evidence, RED/GREEN evidence, and explicit statement that CI provider calls remain zero. Do not merge without explicit MERGE GO.
