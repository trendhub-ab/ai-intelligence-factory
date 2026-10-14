# V2-005 Live Selection / Evidence Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the existing V2 live selection + rank-1 Evidence path on real Hacker News/arXiv candidates with safe measurable artifacts and a 3–5-run human-reviewed evidence pack, without granting any Production mutation authority.

**Architecture:** Add a thin V2-005 measurement wrapper around the already-merged V2-004 provider-backed shadow observation and a separate deterministic offline evidence-pack aggregator. Preserve the existing acquisition, ranking, Evidence provider, ChatOps command, workflow trigger, model, request budget, retry/fallback behavior, and V1 Production authority. V2-005 is a falsifiable proof stage: an unsuccessful live result is valid evidence and must not be repaired by widening sources, adding retries, adding rank fallback, or changing selection logic in this slice.

**Tech Stack:** Python 3.11.16, pytest 8.4.2, requests, GitHub Actions, existing AIIF V2 shadow modules, Gemini Generative Language REST API.

**Spec:** `docs/superpowers/specs/2026-10-15-aiif-v2-rebuild-design.md`

**Base Production main:** `fd2841a2d8174c75a68548c2f0f60eca2a9dff58`

**Design branch at planning start:** `design/v2-rebuild-architecture-20261015`

## Global Constraints

- V1 remains Production authority throughout V2-005.
- No Notion, note, Ready, delivery-ledger, subscriber, Economic State, publication, or Production mutation is permitted.
- Use only the currently implemented bounded Hacker News + arXiv live acquisition surface; do not add a source/provider in V2-005.
- Rank 1 only receives Evidence evaluation.
- Gemini model remains exactly `gemini-3.6-flash`.
- Maximum provider-backed Evidence requests per live proof run remains exactly 1.
- Retry count remains 0.
- Model fallback remains 0.
- Rank fallback remains 0; an insufficient/failed rank-1 result is a valid no-winner result.
- Preserve the current provider timeout contract (`PROVIDER_TIMEOUT_SECONDS = 120.0`) unless a separate approved design changes it.
- Do not persist API keys, request headers, prompts, candidate description/abstract, raw provider response bodies, raw transport exception text, or arbitrary provider payloads.
- The safe live-proof artifact may persist only the bounded candidate review fields listed in Task 2 plus existing V2 diagnostic fields.
- Gemini usage metadata is observational only. Missing or malformed usage metadata must not convert an otherwise valid Evidence result into failure.
- Do not hard-code currency cost/pricing in V2-005. Persist request/token counts only; calculate current monetary cost during human review using then-current official pricing.
- V2-005 requires 3–5 independent live proof runs before an evidence pack may be considered reviewable.
- There is no automatic promotion. Every evidence pack ends with `promotion_decision = "human_review_required"`.
- No live provider call during implementation or offline verification. Live runs occur only after code review/merge approval and a separate explicit operational go-ahead.
- No merge into `main` without the current repository verification gates and explicit `MERGE GO`.

## File Structure

- Create `v2_005_live_proof.py` — thin measurement/orchestration wrapper over existing `GeminiEvidenceProvider` + `build_provider_backed_observation`; captures only safe candidate review context and numeric usage metadata.
- Create `v2_005_evidence_pack.py` — pure offline validator/aggregator for 3–5 V2-005 run artifacts plus optional human V1-comparison review input; performs no network/model/Production work.
- Create `tests/test_v2_005_live_proof.py` — focused TDD contract for the live-proof wrapper and non-leakage rules.
- Create `tests/test_v2_005_evidence_pack.py` — focused TDD contract for evidence-pack validation, aggregation, determinism, and no-auto-promotion.
- Modify `.github/workflows/v2-shadow-deep-dive.yml` — preserve its exact manual/ChatOps contract but run the V2-005 wrapper and include V2-005 focused tests.
- Modify `tests/test_v2_shadow_deep_dive_workflow.py` — pin the workflow to the V2-005 wrapper while preserving exact command, confirmation token, permissions, secret boundary, pinned actions, artifact path, and 14-day retention.
- Modify `AI_Intelligence_Factory_最終仕様書.md` only if the repository freshness/fingerprint guard requires the Production Contract Fingerprint to be refreshed because the workflow surface changed.
- Do not modify `v2_shadow_selection.py`, `v2_live_shadow_acquisition.py`, or selection/ranking rules in V2-005 unless an existing regression test proves an implementation defect unrelated to V2-005 scope; if such a defect appears, stop and re-design rather than silently expanding scope.

## Review Focus

1. **Provider success with absent/malformed `usageMetadata`:** Evidence success/failure semantics must remain unchanged; persisted usage becomes `null`, never a provider failure. Task 2 owns this test.
2. **Sensitive-data leakage through measurement:** candidate `description`, request prompt, API key/header, raw provider response, and secret-bearing exception text must never enter the V2-005 measurement artifact. Task 2 owns this test.
3. **Invalid evidence-pack cardinality/identity:** fewer than 3 runs, more than 5 runs, or duplicate `run_id` values must fail closed rather than producing a review pack. Task 4 owns this test.
4. **Unsafe/non-shadow run mixed into pack:** any input that does not prove `production_authority == "v1"`, `diagnostic_only is True`, provider request budget <= 1, and `promotion_decision == "human_review_required"` must fail closed. Task 4 owns this test.
5. **Human review mismatch:** unknown run IDs, invalid verdict enums, non-string/overlong rationale, or duplicated review entries must fail closed; missing review is allowed but reported as not reviewed. Task 4 owns this test.

---

### Task 1: Lock the V2-005 Live-Proof Contract with RED Tests

**Files:**
- Create: `tests/test_v2_005_live_proof.py`
- Read only for reference: `v2_shadow_observation.py`, `v2_live_shadow_acquisition.py`, `v2_shadow_selection.py`

**Interfaces:**
- Consumes: existing `GeminiEvidenceProvider`, `build_provider_backed_observation`, `write_observation`, `LiveAcquisitionConfig`.
- Produces test contract for Task 2 interfaces:
  - `build_live_proof(*, now: datetime, run_id: str, api_key: str, config: LiveAcquisitionConfig | None = None, http_get: Callable[..., Any] = requests.get, http_post: Callable[..., Any] = requests.post, v1_reference: str | None = None) -> dict[str, Any]`
  - `write_live_proof(report: Mapping[str, Any], output_path: str | Path) -> Path`

- [ ] **Step 1: Create the RED test module with one successful deterministic fixture**

Test name: `test_live_proof_records_safe_rank1_measurement_with_one_provider_request`.

Assertions must pin:
- exactly one POST call;
- existing model remains `gemini-3.6-flash`;
- existing Evidence request timeout remains `120.0`;
- V2-selected identity equals the measured candidate identity when Evidence is sufficient;
- `v2_005_measurement.proof_version == "V2-005"`;
- `production_mutation_authorized is False`;
- `promotion_decision == "human_review_required"`;
- safe evaluated-candidate fields are exactly `candidate_identity`, `provider`, `title`, `source_timestamp`, `screening_score`, `screening_reasons`;
- provider request count is exactly 1.

- [ ] **Step 2: Add RED tests for Gemini usage metadata**

Test names:
- `test_live_proof_records_numeric_provider_usage_when_present`
- `test_live_proof_tolerates_missing_usage_metadata`
- `test_live_proof_tolerates_malformed_usage_metadata`

Accepted persisted usage shape when valid:

```python
{
    "prompt_token_count": 123,
    "candidate_token_count": 45,
    "total_token_count": 168,
}
```

Missing/malformed usage must persist as `None` and must not change the Evidence result category.

- [ ] **Step 3: Add RED non-leakage and fail-closed tests**

Test names:
- `test_live_proof_does_not_persist_description_prompt_key_headers_or_raw_provider_body`
- `test_live_proof_preserves_safe_provider_failure_classification_without_retry`
- `test_live_proof_insufficient_rank1_never_rescues_rank2`
- `test_live_proof_keeps_v1_authority_and_diagnostic_only_boundary`

Use sentinel strings such as `SECRET_DESCRIPTION`, `SECRET_KEY`, `SECRET_PROVIDER_BODY`, and `SECRET_TRANSPORT_DETAIL`, then assert none occur in `json.dumps(report, ensure_ascii=False)`.

- [ ] **Step 4: Run the focused tests and prove RED**

Run:

```bash
python -m pytest -q tests/test_v2_005_live_proof.py
```

Expected: FAIL during import because `v2_005_live_proof` does not yet exist.

- [ ] **Step 5: Commit the RED contract**

```bash
git add tests/test_v2_005_live_proof.py
git commit -m "test: define V2-005 live proof contract"
```

---

### Task 2: Implement the Thin Safe Live-Proof Measurement Wrapper

**Files:**
- Create: `v2_005_live_proof.py`
- Test: `tests/test_v2_005_live_proof.py`
- Do not modify: `v2_shadow_selection.py`, `v2_live_shadow_acquisition.py`

**Interfaces:**
- Consumes:
  - `GeminiEvidenceProvider(api_key=..., model="gemini-3.6-flash", http_post=...)`
  - `build_provider_backed_observation(..., deep_dive=recording_deep_dive, ...) -> dict[str, Any]`
  - existing `write_observation(...)` semantics for deterministic JSON.
- Produces:
  - `build_live_proof(...) -> dict[str, Any]`
  - `write_live_proof(report, output_path) -> Path`
  - CLI: `python v2_005_live_proof.py --output <path> --run-id <id>` using `GEMINI_API_KEY` from the environment only.

- [ ] **Step 1: Implement safe numeric usage extraction**

Add internal interface:

```python
def extract_usage_metadata(body: Any) -> dict[str, int] | None:
    ...
```

Accept only non-boolean integers >= 0 from Gemini `usageMetadata` keys `promptTokenCount`, `candidatesTokenCount`, and `totalTokenCount`. Require all three numeric fields for a persisted usage object; otherwise return `None`. Do not preserve any other provider response field.

- [ ] **Step 2: Implement an in-memory `http_post` recorder without a second provider request**

Add an internal callable wrapper that:
- delegates exactly once to the injected/default `http_post`;
- reads `response.json()` only to extract numeric `usageMetadata`;
- stores only the normalized numeric usage object or `None`;
- returns the original response unchanged so the existing `GeminiEvidenceProvider` performs its existing strict parsing and failure classification.

The recorder must not catch/replace provider transport failures; the existing provider remains the authority for safe error classification.

- [ ] **Step 3: Implement `build_live_proof` by injecting a recording Deep Dive**

Create one existing `GeminiEvidenceProvider` and a `recording_deep_dive(candidate)` closure. Before delegating, copy only these review fields from rank 1:
- `candidate_identity`
- `provider`
- `title`
- `source_timestamp`
- `screening_score`
- `screening_reasons`

Then delegate to the existing provider exactly once. Pass that closure into existing `build_provider_backed_observation`; do not duplicate acquisition, scoring, ranking, Evidence parsing, provider failure classification, or winner logic.

Append exactly one new top-level object:

```python
"v2_005_measurement": {
    "proof_version": "V2-005",
    "evaluated_candidate": safe_candidate_or_none,
    "provider_usage": normalized_usage_or_none,
    "provider_request_count": actual_deep_dive_count,
    "production_mutation_authorized": False,
    "promotion_decision": "human_review_required",
}
```

Derive `provider_request_count` from the report's existing `actual_calls.deep_dive`, not from an assumed constant.

- [ ] **Step 4: Implement deterministic writer and CLI**

`write_live_proof` may delegate to existing `write_observation` rather than creating a second JSON serialization policy.

CLI requirements:
- `--run-id` required;
- `--output` defaults to `article_audit/v2_shadow_deep_dive.json` to preserve the workflow artifact path;
- API key read only from `GEMINI_API_KEY` environment variable;
- current UTC time supplied to `build_live_proof`;
- no new CLI option may select a model, source, retry count, rank, arbitrary prompt, workflow, or Production destination.

- [ ] **Step 5: Run focused GREEN**

```bash
python -m pytest -q tests/test_v2_005_live_proof.py
```

Expected: PASS, zero failures.

- [ ] **Step 6: Run V2-004 regression coverage**

```bash
python -m pytest -q \
  tests/test_v2_shadow_deep_dive.py \
  tests/test_v2_shadow_provider_diagnostics.py \
  tests/test_v2_shadow_provider_http_diagnostics.py \
  tests/test_v2_live_shadow_acquisition_budget.py
```

Expected: PASS, proving V2-005 measurement did not alter V2-004 Evidence semantics or the one-attempt budget.

- [ ] **Step 7: Commit the implementation**

```bash
git add v2_005_live_proof.py tests/test_v2_005_live_proof.py
git commit -m "feat: add measured V2-005 live proof wrapper"
```

---

### Task 3: Lock the 3–5 Run Evidence-Pack Contract with RED Tests

**Files:**
- Create: `tests/test_v2_005_evidence_pack.py`

**Interfaces:**
- Consumes V2-005 live-proof JSON objects from Task 2.
- Produces test contract for Task 4:
  - `build_evidence_pack(reports: Sequence[Mapping[str, Any]], human_reviews: Mapping[str, Any] | None = None) -> dict[str, Any]`
  - `render_evidence_pack_markdown(pack: Mapping[str, Any]) -> str`
  - `write_evidence_pack(pack: Mapping[str, Any], *, json_path: str | Path, markdown_path: str | Path) -> tuple[Path, Path]`

- [ ] **Step 1: Add RED tests for cardinality and unique-run validation**

Test names:
- `test_evidence_pack_accepts_three_valid_unique_runs`
- `test_evidence_pack_accepts_five_valid_unique_runs`
- `test_evidence_pack_rejects_fewer_than_three_runs`
- `test_evidence_pack_rejects_more_than_five_runs`
- `test_evidence_pack_rejects_duplicate_run_ids`

Use fixed deterministic run fixtures. The aggregate must never silently drop excess/duplicate inputs.

- [ ] **Step 2: Add RED tests for shadow-safety invariants**

Test name: `test_evidence_pack_rejects_any_run_without_v1_shadow_safety_proof`.

Parameterize invalid inputs for:
- observation mode not `provider_backed_one_shot`;
- `production_authority != "v1"`;
- `diagnostic_only is not True`;
- request budget > 1;
- `actual_calls.deep_dive > 1`;
- `v2_005_measurement.provider_request_count > 1`;
- `production_mutation_authorized is not False`;
- `promotion_decision != "human_review_required"`.

- [ ] **Step 3: Add RED aggregation tests**

Test name: `test_evidence_pack_aggregates_winners_evidence_failures_requests_and_tokens`.

Pin output fields:
- `proof_version: "V2-005"`;
- `run_count`;
- `winner_count`;
- `evidence_sufficient_count`;
- `evidence_insufficient_count`;
- `provider_failure_count`;
- `provider_request_count_total`;
- token totals only from valid numeric usage records;
- `provider_usage_observed_run_count`;
- safe provider error-code counts;
- deterministic `runs` ordered by `run_id`;
- `promotion_decision: "human_review_required"`.

Do not infer monetary cost.

- [ ] **Step 4: Add RED human-review validation tests**

Human-review input schema per run:

```json
{
  "<run_id>": {
    "v1_candidate_identity": "https://example.com/or-null",
    "verdict": "v2_better | equivalent | v1_better | not_comparable",
    "rationale": "short human review"
  }
}
```

Test names:
- `test_evidence_pack_accepts_optional_valid_human_v1_comparison`
- `test_evidence_pack_rejects_unknown_human_review_run_id`
- `test_evidence_pack_rejects_invalid_verdict`
- `test_evidence_pack_rejects_non_string_or_overlong_rationale`
- `test_evidence_pack_marks_missing_human_review_as_not_reviewed`

Normalize rationale whitespace and cap at 1000 characters. `v1_candidate_identity` may be a non-empty string or `None` only.

- [ ] **Step 5: Add RED determinism/no-auto-promotion tests**

Test names:
- `test_evidence_pack_json_is_deterministic_for_input_order`
- `test_evidence_pack_markdown_is_deterministic_and_never_auto_promotes`

The Markdown must end with an explicit human-review requirement and must not emit an automatic GO/NO-GO conclusion for V2-006.

- [ ] **Step 6: Run focused tests and prove RED**

```bash
python -m pytest -q tests/test_v2_005_evidence_pack.py
```

Expected: FAIL during import because `v2_005_evidence_pack` does not yet exist.

- [ ] **Step 7: Commit the RED contract**

```bash
git add tests/test_v2_005_evidence_pack.py
git commit -m "test: define V2-005 evidence pack contract"
```

---

### Task 4: Implement the Deterministic Offline Evidence-Pack Aggregator

**Files:**
- Create: `v2_005_evidence_pack.py`
- Test: `tests/test_v2_005_evidence_pack.py`

**Interfaces:**
- Consumes exact Task 3 fixtures/contracts.
- Produces:
  - `build_evidence_pack(...) -> dict[str, Any]`
  - `render_evidence_pack_markdown(...) -> str`
  - `write_evidence_pack(...) -> tuple[Path, Path]`
  - CLI accepting 3–5 report paths and optional `--human-review <json>`; outputs JSON + Markdown only.

- [ ] **Step 1: Implement strict run validation**

Validate cardinality before aggregation. Extract `run_id` from each report's existing run metadata and reject missing/blank/duplicate IDs. Validate every shadow-safety invariant pinned in Task 3 before calculating any summary.

Use a dedicated `EvidencePackContractError(ValueError)` so malformed inputs fail closed with a local deterministic error, not partial output.

- [ ] **Step 2: Implement deterministic aggregate counters**

Aggregate only safe fields already present in V2-005 reports. Provider failure aggregation must use safe machine-readable categories already emitted by V2-004; do not copy raw exception/provider text.

Token totals must sum only complete valid `provider_usage` records and report how many runs had observable usage. Absence of usage is not converted to zero-token certainty.

- [ ] **Step 3: Implement human-review validation/merge**

Allow only verdicts:
- `v2_better`
- `equivalent`
- `v1_better`
- `not_comparable`

Unknown run IDs fail closed. A run with no review gets `review_status: "not_reviewed"`; a valid review gets `review_status: "reviewed"`. Human rationale is normalized whitespace and max 1000 characters.

- [ ] **Step 4: Implement deterministic JSON and Markdown writers**

JSON: UTF-8, sorted keys, stable separators, one trailing newline.

Markdown: concise table/sections containing run ID, V2 candidate identity/title/provider, Evidence outcome, request/token observation, safe failure code, optional V1 candidate identity, verdict, rationale. End with:

`Promotion decision: HUMAN REVIEW REQUIRED — this evidence pack cannot authorize V2-006 automatically.`

- [ ] **Step 5: Run focused GREEN**

```bash
python -m pytest -q tests/test_v2_005_evidence_pack.py
```

Expected: PASS, zero failures.

- [ ] **Step 6: Commit the implementation**

```bash
git add v2_005_evidence_pack.py tests/test_v2_005_evidence_pack.py
git commit -m "feat: add V2-005 human-reviewed evidence pack"
```

---

### Task 5: Wire the Existing Manual Workflow Without Changing ChatOps Authority

**Files:**
- Modify: `.github/workflows/v2-shadow-deep-dive.yml`
- Modify: `tests/test_v2_shadow_deep_dive_workflow.py`
- Do not modify unless a test proves necessary: `.github/workflows/chatops-one-shot.yml`, `run202_chatops_control.py`

**Interfaces:**
- Consumes existing exact ChatOps command `/aiif run v2_shadow_deep_dive` and downstream payload targeting `v2-shadow-deep-dive.yml` with `RUN_V2_SHADOW_DEEP_DIVE` on `main`.
- Produces the same diagnostic artifact path `article_audit/v2_shadow_deep_dive.json`, now generated by `v2_005_live_proof.py`.

- [ ] **Step 1: Change workflow-contract tests first**

Update `test_v2_workflow_receives_only_model_secret_and_writes_diagnostic_artifact` to require `v2_005_live_proof.py` and prohibit direct execution of `v2_shadow_observation.py` in the workflow run step.

Add/retain assertions that:
- `workflow_dispatch` only; no `schedule` or `push`;
- exact confirmation token `RUN_V2_SHADOW_DEEP_DIVE`;
- `contents: read`, never `contents: write`;
- only `GEMINI_API_KEY` is supplied to the observation step;
- no Notion/note/Production credentials or Production pipeline entrypoints;
- checkout/setup-python pins remain unchanged;
- artifact path remains `article_audit/v2_shadow_deep_dive.json`;
- artifact retention remains 14 days;
- exact ChatOps command/target/payload remains unchanged.

- [ ] **Step 2: Run workflow test and prove RED**

```bash
python -m pytest -q tests/test_v2_shadow_deep_dive_workflow.py
```

Expected: FAIL because the workflow still invokes `v2_shadow_observation.py`.

- [ ] **Step 3: Make the minimal workflow change**

Replace only the execution command with:

```bash
python v2_005_live_proof.py \
  --output article_audit/v2_shadow_deep_dive.json \
  --run-id "v2-deep-dive-${{ github.run_id }}-${{ github.run_attempt }}"
```

Extend the workflow's focused safety test step to include:
- `tests/test_v2_005_live_proof.py`
- existing `tests/test_v2_live_shadow_acquisition_budget.py`
- existing `tests/test_v2_shadow_deep_dive.py`
- existing `tests/test_v2_shadow_deep_dive_workflow.py`
- existing provider diagnostic tests if runtime remains acceptable.

Do not add evidence-pack aggregation to this workflow; each run must remain one independent proof artifact.

- [ ] **Step 4: Run workflow and combined focused GREEN**

```bash
python -m pytest -q \
  tests/test_v2_005_live_proof.py \
  tests/test_v2_005_evidence_pack.py \
  tests/test_v2_live_shadow_acquisition_budget.py \
  tests/test_v2_shadow_deep_dive.py \
  tests/test_v2_shadow_provider_diagnostics.py \
  tests/test_v2_shadow_provider_http_diagnostics.py \
  tests/test_v2_shadow_deep_dive_workflow.py
```

Expected: PASS, zero failures.

- [ ] **Step 5: Commit workflow wiring**

```bash
git add .github/workflows/v2-shadow-deep-dive.yml tests/test_v2_shadow_deep_dive_workflow.py
git commit -m "ci: route V2 shadow deep dive through V2-005 proof"
```

---

### Task 6: Offline Integration, Production-Isolation, and Canonical Contract Verification

**Files:**
- Potentially modify: `AI_Intelligence_Factory_最終仕様書.md` only if the existing canonical freshness guard reports a new required fingerprint.
- No other scope expansion is permitted in this task.

**Interfaces:**
- Consumes all Task 1–5 code/tests.
- Produces a branch that is ready for repository CI review, not a live proof result.

- [ ] **Step 1: Compile the touched Python surfaces**

```bash
python -m py_compile \
  v2_005_live_proof.py \
  v2_005_evidence_pack.py \
  v2_shadow_observation.py \
  v2_live_shadow_acquisition.py \
  v2_shadow_selection.py
```

Expected: exit 0.

- [ ] **Step 2: Run the complete focused V2-005/V2-004 regression set**

Run the combined focused command from Task 5 Step 4.

Expected: PASS, zero failures.

- [ ] **Step 3: Run the full deterministic repository suite**

```bash
python -m pytest -q
```

Expected: exit 0, zero failures. Record the exact pass/subtest counts from this run; do not reuse historical counts.

- [ ] **Step 4: Run existing repository guards/CI locally where their repository entrypoints exist**

At minimum verify the contracts represented by the repository's existing CI checks:
- Workflow Reference Guard;
- Repository Falsification Guard;
- Integration Stability Guard;
- Canonical Specification Freshness Guard;
- Notion Access Policy Guard;
- synthetic Production smoke.

Do not invent replacement scripts. Use the existing repository commands/workflows exactly as currently defined. If a local guard is not independently invokable, leave it for PR CI and state that explicitly in the PR evidence.

- [ ] **Step 5: Refresh only the canonical fingerprint if the existing guard requires it**

If and only if the canonical freshness guard reports a stale Production Contract Fingerprint because `.github/workflows/v2-shadow-deep-dive.yml` changed, update only the fingerprint value in `AI_Intelligence_Factory_最終仕様書.md` using the repository's existing guard-computed value. Re-run the failing guard/full test after the update.

Do not rewrite the V1 Production specification to claim V2-005 has Production authority.

- [ ] **Step 6: Inspect the final diff for forbidden surfaces**

The diff must contain no additions that import/call or add credentials for:
- Notion writers;
- note writers;
- Production pipeline entrypoints;
- Ready-state mutation;
- delivery queue/ledger mutation;
- subscriber/member mutation;
- arbitrary model/source/prompt selection.

Also confirm `v2_shadow_selection.py` and `v2_live_shadow_acquisition.py` remain unchanged unless implementation was stopped for re-design.

- [ ] **Step 7: Commit any fingerprint-only reconciliation**

If required:

```bash
git add AI_Intelligence_Factory_最終仕様書.md
git commit -m "docs: refresh contract fingerprint for V2-005 proof"
```

If not required, make no empty commit.

---

### Task 7: Draft PR Readiness and Offline Evidence Review

**Files:**
- No code changes expected.

**Interfaces:**
- Consumes verified branch from Task 6.
- Produces a Draft PR/review packet; does not merge and does not call Gemini live.

- [ ] **Step 1: Compare branch against current `main` before opening/updating PR**

Confirm the branch base has not silently diverged in a way that changes V2-005 assumptions. If `main` advanced, reconcile deliberately and re-run Task 6 verification after reconciliation.

- [ ] **Step 2: Open or update a Draft PR**

PR summary must state:
- V2-005 is diagnostic-only;
- no live provider call was made during implementation;
- no Production mutation authority was added;
- HN/arXiv only;
- rank 1 only;
- Gemini 3.6 Flash only;
- max one request/run, retry 0, fallback 0;
- no ranking/selection change;
- evidence pack requires 3–5 independent runs and human review;
- exact fresh test/CI evidence.

- [ ] **Step 3: Stop at the merge gate**

Do not merge without explicit `MERGE GO`.

---

### Task 8: Post-Merge Live-Proof Operating Procedure — Execute Only After Separate Explicit Approval

**Files:**
- Runtime artifacts only; no code change.

**Interfaces:**
- Consumes merged/reviewed V2-005 workflow.
- Produces 3–5 independent live-proof JSON artifacts, then one offline evidence pack for human review.

- [ ] **Step 1: Run one live proof through the existing manual/ChatOps path**

Use the existing exact command/workflow contract. One run may perform at most one Gemini Evidence request.

- [ ] **Step 2: Inspect the first artifact before spending more provider calls**

Verify:
- V1 authority;
- diagnostic-only state;
- request count <= 1;
- no sensitive fields;
- safe candidate context present when a rank-1 candidate was evaluated;
- provider usage either safe numeric metadata or `null`;
- no unexpected Production mutation evidence.

If this fails, stop. Do not run the remaining proof set.

- [ ] **Step 3: Collect 3–5 independent runs**

Do not batch them into one workflow execution and do not widen sources/retries to manufacture success. A no-winner/provider-failure/insufficient-Evidence run remains part of the evidence set.

- [ ] **Step 4: Perform human V1 comparison**

For each run, identify the comparable V1 choice when reasonably available and record one verdict:
- `v2_better`
- `equivalent`
- `v1_better`
- `not_comparable`

Review the actual linked source manually when judging topic/article value and source traceability. Important limitation: the current V2-004 Gemini Evidence prompt judges supplied candidate metadata only and does not itself browse/fetch article bodies; V2-005 must expose that limitation rather than mislabel metadata judgment as independently verified primary-source reading.

- [ ] **Step 5: Build the offline evidence pack**

Run `v2_005_evidence_pack.py` with the 3–5 run files and optional human-review JSON. Confirm the pack remains `human_review_required` regardless of counts.

- [ ] **Step 6: Make the human promotion decision**

Review:
- topic/article value;
- Evidence sufficiency and the metadata-only limitation;
- primary-source traceability by manual inspection;
- V1 comparison verdicts;
- request count and observed token usage;
- safe failure patterns;
- whether one request/run is sufficient.

Only an explicit human decision may authorize design/planning for V2-006. If V2-005 exposes that metadata-only Evidence is inadequate, design the smallest source-content Evidence improvement as a new approved slice rather than weakening the V2-005 proof criteria.

---

## Final Verification Checklist Before Any Completion Claim

- [ ] Fresh focused V2-005/V2-004 tests are GREEN.
- [ ] Fresh full `pytest -q` is GREEN with exact counts recorded.
- [ ] Relevant repository guards/PR CI are GREEN or any unavailable local-only checks are explicitly left pending for CI.
- [ ] Diff contains no Production writer/mutation authority.
- [ ] Workflow remains manual-only and `contents: read`.
- [ ] ChatOps command, workflow name, confirmation token, artifact path, and secret boundary remain compatible.
- [ ] No live Gemini call occurred during implementation verification.
- [ ] No merge occurred without explicit `MERGE GO`.
- [ ] Post-merge live proof, when separately authorized, collects 3–5 independent runs and never auto-promotes V2-006.
