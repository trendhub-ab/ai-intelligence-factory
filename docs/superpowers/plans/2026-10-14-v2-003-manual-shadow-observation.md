# V2-003 Manual Shadow Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual, zero-model V2 observation path that runs bounded live HN/arXiv acquisition, exposes deterministic pre-Deep-Dive ranking as diagnostic evidence, and writes one ephemeral JSON artifact without granting V2 any Production authority.

**Architecture:** Make the smallest backward-compatible V2-002 extension so callers may explicitly set Deep Dive budget to `0` or `1`; V2-003 always uses `0`. A focused `v2_shadow_observation.py` runner derives `pre_deep_dive_leader`, validates the zero-model/no-winner contract, and writes one JSON report. A manual-only GitHub Actions workflow runs the focused safety tests, executes the runner, and uploads the artifact with read-only repository permissions.

**Tech Stack:** Python 3.11.16, stdlib, `requests` through existing V2-002, pytest 8.4.2, GitHub Actions pinned checkout/setup-python actions and upload-artifact.

**Spec:** `docs/superpowers/specs/2026-10-14-v2-003-manual-shadow-observation-design.md`

## Global Constraints

- Core invariant: **V2は観測する。まだ決定しない。V1には触れない。**
- Base main is `14d37baaaaa976aa8774329e98114a804db49e9f`.
- V1 remains the sole Production authority.
- V2-003 paid/model calls: `0`; Gemini calls: `0`; OpenAI calls: `0`.
- V2-003 Notion calls: `0`; note/browser automation: `0`; new secrets: `0`.
- HN/arXiv acquisition remains bounded by V2-002 maxima: HN `8`, arXiv `8`, combined `12`, timeout `8s` maximum.
- V2-002 default Deep Dive behavior remains `1`; V2-003 explicitly requests `0`.
- With Deep Dive disabled, `v2_selected_candidate_identity` remains absent/null and no candidate may be called a winner/selected/ready/recommended result.
- Workflow trigger is `workflow_dispatch` only, with typed confirmation `RUN_V2_SHADOW_OBSERVATION` and `permissions: contents: read`.
- No `schedule`, `push`, Production workflow call, commit/push, PR/issue/comment mutation, persistent state, cache, database or queue.
- Exactly one JSON observation file is produced at the caller-supplied path; workflow default is `article_audit/v2_shadow_observation.json`.
- Source outages are observed fail-closed conditions and do not by themselves make the workflow infrastructure fail.
- `pipeline.py`, Daily/Fresh/Rolling, Notion/note, Ready state, article generation/publication and Economic State are out of scope.
- Merge remains separately gated by explicit `MERGE GO`.

## Review Focus

- **Deep-Dive budget coercion:** negative, zero, one and values above one must resolve to the intended `0/1` contract without changing the V2-002 default; Task 1 pins all four cases.
- **No-candidate/source-outage runs:** a valid fail-closed report must still serialize and upload, with leader `null`, zero Deep Dive calls and no workflow failure caused only by source availability; Task 2/3 pin this.
- **Misleading selection language:** observation output must never turn rank 1 into a winner when Deep Dive is zero; Task 2 asserts both winner absence and the exact `pre_deep_dive_leader` field.
- **Credential/authority creep in workflow:** a later edit must not add secrets, write permissions, automatic triggers or Production workflow calls; Task 3 static contract tests pin these surfaces.
- **Artifact determinism/leakage:** fixed source fixtures, clock and run id must produce byte-stable JSON and must not include raw provider exception text/private article data; Task 2 pins deterministic serialization and leakage boundaries.

---

### Task 1: Add the explicit zero/one Deep Dive budget at the V2-002 boundary

**Files:**
- Modify: `v2_live_shadow_acquisition.py`
- Modify: `tests/test_v2_live_shadow_acquisition.py`

**Interfaces:**
- Consumes: existing `run_shadow_selection(..., config=ShadowConfig(...))`.
- Produces: `run_bounded_live_shadow(..., max_deep_dive_attempts: int = 1, ...) -> dict[str, Any]`.
- Contract: normalize caller budget to `0` when `int(value) <= 0`, otherwise `1`; invalid/non-coercible values fail closed to `0`. Default remains exactly `1`.

- [ ] **Step 1: Write failing budget tests**

Add tests named around these assertions:
- omitted `max_deep_dive_attempts` preserves one-attempt V2-002 behavior;
- explicit `0` invokes a sentinel Deep Dive callable zero times and reports `deep_dive_attempted_count == 0` and `actual_calls["deep_dive"] == 0`;
- negative/invalid values clamp fail-closed to `0`;
- values `1` and greater clamp to `1`.

- [ ] **Step 2: Run RED verification**

Run: `python -m pytest -q tests/test_v2_live_shadow_acquisition.py`
Expected: new tests FAIL because `run_bounded_live_shadow` does not yet accept the budget parameter.

- [ ] **Step 3: Implement the minimal backward-compatible parameter**

Modify `run_bounded_live_shadow` to accept `max_deep_dive_attempts: int = 1`, normalize it once, and pass the normalized value into `ShadowConfig(max_deep_dive_attempts=...)`. Do not change source limits, provider order, selection logic, or default behavior.

- [ ] **Step 4: Run GREEN verification**

Run: `python -m pytest -q tests/test_v2_live_shadow_acquisition.py tests/test_v2_live_shadow_acquisition_fixture.py`
Expected: all V2-002 tests PASS, including the existing one-Deep-Dive fixture.

- [ ] **Step 5: Commit**

Commit message: `feat: allow zero-budget V2 shadow acquisition`

---

### Task 2: Build the zero-model observation runner and deterministic artifact contract

**Files:**
- Create: `v2_shadow_observation.py`
- Create: `tests/test_v2_shadow_observation.py`
- Create: `tests/v2_shadow_observation_fixture.py`
- Create: `tests/test_v2_shadow_observation_fixture.py`

**Interfaces:**
- Consumes: `LiveAcquisitionConfig`, `run_bounded_live_shadow(..., max_deep_dive_attempts=0)`.
- Produces: `derive_pre_deep_dive_leader(report: Mapping[str, Any]) -> dict[str, Any] | None`.
- Produces: `build_manual_observation(*, now: datetime, run_id: str, config: LiveAcquisitionConfig | None = None, http_get: Callable[..., Any] = requests.get) -> dict[str, Any]`.
- Produces: `write_observation(report: Mapping[str, Any], output_path: str | Path) -> Path`.
- CLI contract: `python v2_shadow_observation.py --output article_audit/v2_shadow_observation.json --run-id <opaque-id>`; the CLI supplies current UTC time and uses public GETs only.

- [ ] **Step 1: Write failing runner contract tests**

Tests must assert:
- `build_manual_observation` always passes Deep Dive budget `0`; use a sentinel callback path that raises if unexpectedly invoked;
- `deep_dive_attempted_count == 0`, `actual_calls.deep_dive == 0`, and `v2_selected_candidate_identity is None`;
- `observation.mode == "manual_zero_model"` (or an equally explicit fixed metadata field defined once in the implementation);
- `pre_deep_dive_leader` equals only `candidate_identity`, `provider`, `screening_score`, `eligible` from the first screening row;
- empty screening gives `pre_deep_dive_leader is None`;
- one-source and both-source failure still return valid reports instead of raising due only to source availability;
- raw transport text such as `do not leak this text` never appears in the observation report.

- [ ] **Step 2: Run RED verification**

Run: `python -m pytest -q tests/test_v2_shadow_observation.py`
Expected: FAIL because `v2_shadow_observation` does not exist.

- [ ] **Step 3: Implement the minimal runner**

Implement the three interfaces above. The runner may create the parent of `output_path` and may write that one file only; it must not scan/read prior observation history or create secondary state. Use UTF-8 JSON with deterministic key ordering and a terminating newline so fixed inputs are byte-stable.

- [ ] **Step 4: Add deterministic fixture proof**

Reuse or mirror the existing V2-002 injected HTTP fixture shapes in `tests/v2_shadow_observation_fixture.py`. Fix time and run id. Assert both HN and arXiv flow through V2-001/V2-002, leader is deterministic, winner remains null, Deep Dive is zero, and repeated serialized output bytes are identical.

- [ ] **Step 5: Run focused GREEN verification**

Run: `python -m pytest -q tests/test_v2_live_shadow_acquisition.py tests/test_v2_shadow_observation.py tests/test_v2_shadow_observation_fixture.py`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add zero-model V2 shadow observation runner`

---

### Task 3: Lock Production isolation and add the manual observation workflow

**Files:**
- Create: `.github/workflows/v2-shadow-observation.yml`
- Create: `tests/test_v2_shadow_observation_boundary.py`
- Create: `tests/test_v2_shadow_observation_workflow.py`

**Interfaces:**
- Workflow name: `V2 Shadow Observation [ZERO MODEL]`.
- Trigger: top-level `workflow_dispatch` only.
- Required input: `confirm`; job runs only when `inputs.confirm == 'RUN_V2_SHADOW_OBSERVATION'`.
- Permissions: `contents: read` only.
- Runner command writes `article_audit/v2_shadow_observation.json`.
- Artifact retention: `14` days; `if-no-files-found: error` because missing output is a contract failure.

- [ ] **Step 1: Write failing AST/source boundary tests**

`tests/test_v2_shadow_observation_boundary.py` must prove `v2_shadow_observation.py`:
- imports V2-002 but not `pipeline`, Notion, note, persistence/publication, model provider SDKs;
- exposes no mutating HTTP method calls;
- imports/uses no `subprocess` and contains no git mutation path;
- performs filesystem mutation only through the explicit observation output helper (`mkdir` for its parent and one `write_text`/equivalent for the requested path), with no secondary persistence target.

- [ ] **Step 2: Write failing workflow contract tests**

`tests/test_v2_shadow_observation_workflow.py` must read `.github/workflows/v2-shadow-observation.yml` and assert:
- only `workflow_dispatch` trigger; no `schedule`, `push`, `workflow_run`;
- exact typed confirmation token;
- `permissions` includes `contents: read` and no write permission;
- no `${{ secrets.` reference;
- no `GEMINI_API_KEY`, OpenAI credential, Notion credential, GH_PAT or model provider env;
- no `daily`, `fresh`, `note`, `production_pipeline.py`, `pipeline.py`, or `gh workflow run` execution;
- checkout/setup-python actions use the repository's existing pinned SHAs;
- dependency installation uses `requirements.txt`, `requirements-ci-constraints.txt`, and pytest `8.4.2`;
- focused V2 safety tests run before the live runner;
- artifact path is exactly `article_audit/v2_shadow_observation.json` and retention is 14 days.

- [ ] **Step 3: Run RED verification**

Run: `python -m pytest -q tests/test_v2_shadow_observation_boundary.py tests/test_v2_shadow_observation_workflow.py`
Expected: workflow tests FAIL because the workflow does not yet exist; boundary tests may expose any accidental runner surface that needs tightening.

- [ ] **Step 4: Implement the manual workflow**

Create the smallest workflow satisfying the interface. Use `ubuntu-latest` or the repository's standard Ubuntu runner, bounded `timeout-minutes`, pinned checkout/setup-python actions, locked dependencies, focused zero-network tests before live execution, then the live observation runner, then `actions/upload-artifact@v7` for the single JSON file. Do not force checkout to `main`; checkout the triggering ref/commit.

- [ ] **Step 5: Run workflow/reference guards locally**

Run:
- `python -m pytest -q tests/test_v2_shadow_observation_boundary.py tests/test_v2_shadow_observation_workflow.py`
- `python workflow_reference_guard.py`
- `python -m unittest tests.test_workflow_reference_guard -v`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `ci: add manual V2 shadow observation workflow`

---

### Task 4: Classify the V2-003 runtime surface, synchronize the canonical fingerprint, and prove repository-wide safety

**Files:**
- Modify: `member_customer_surface_contract.py`
- Modify only as required by freshness guard: `AI_Intelligence_Factory_最終仕様書.md`
- Tests are existing repository guards plus V2-003 focused tests.

**Interfaces:**
- `member_customer_surface_contract.NON_MEMBER_MODULES` must contain `v2_shadow_observation.py` with an explicit V2-003 observation/infrastructure comment; do not weaken classification logic.
- Canonical spec meaning remains unchanged; because root Python/workflow bytes are Production surfaces under `specification_freshness_guard.py`, update `Production最終照合日` only to the guard-derived latest Production date and replace only the `Production Contract Fingerprint` with the guard-produced value unless an actual semantic spec change is discovered.

- [ ] **Step 1: Run the focused repository classification test expecting the new module to be caught if still unclassified**

Run: `python -m unittest tests.test_member_customer_surface_contract.MemberCustomerSurfaceContractTests.test_every_registered_surface_has_owner_audit_and_existing_files -v`
Expected before classification: FAIL with an unclassified module complaint if the guard sees the new root module.

- [ ] **Step 2: Add the one-line non-member classification and rerun**

Expected: PASS without changing any customer/member surface registry or validation rule.

- [ ] **Step 3: Run canonical freshness guard and synchronize only what it requires**

Run: `python specification_freshness_guard.py`
Expected initially after Production-byte changes: FAIL with `production_contract_fingerprint_mismatch` and print the exact expected fingerprint/latest Production date. Update only the metadata required by that output, then rerun until PASS.

- [ ] **Step 4: Run all focused V2-003 tests**

Run: `python -m pytest -q tests/test_v2_live_shadow_acquisition.py tests/test_v2_live_shadow_acquisition_fixture.py tests/test_v2_shadow_observation.py tests/test_v2_shadow_observation_fixture.py tests/test_v2_shadow_observation_boundary.py tests/test_v2_shadow_observation_workflow.py`
Expected: PASS.

- [ ] **Step 5: Run repository guards**

Run:
- `python repository_falsification_guard.py`
- `python workflow_reference_guard.py`
- `python integration_stability_guard.py`
- `python specification_freshness_guard.py`
- `python -m unittest tests.test_member_customer_surface_contract -v`
- `python -m unittest tests.test_workflow_reference_guard -v`
- `python -m unittest tests.test_specification_freshness_guard -v`
- `git diff --check`

Expected: all PASS/exit 0.

- [ ] **Step 6: Run the full deterministic repository suite**

Run: `python -m pytest -q tests test_run360_gemini_retry_owner.py`
Expected: exit 0 with zero failures and no external network access from pytest.

- [ ] **Step 7: Run synthetic Production smoke**

Run with `SYNTHETIC_REGRESSION_MODE=true` and `SYNTHETIC_REGRESSION_TIER=smoke`: `python production_pipeline.py`.
Expected: existing synthetic Production smoke remains GREEN; V2-003 does not participate in Production execution.

- [ ] **Step 8: Commit**

Commit message: `test: verify V2-003 repository isolation`

---

### Task 5: Draft PR, exact-head CI evidence, and bounded manual live proof

**Files:**
- No new Production code unless verification finds a real defect; any defect fix returns to RED/GREEN TDD before this task resumes.
- Update Draft PR description only.

**Interfaces:**
- PR targets `main`, stays Draft, and stays unmerged until separate `MERGE GO`.
- Live proof is manual `workflow_dispatch` only and never Daily/Fresh.

- [ ] **Step 1: Confirm branch ancestry before PR**

Compare branch base/head to current `main`. If main advanced, inspect impact and rebase/merge safely before claiming final evidence; do not silently build on stale assumptions.

- [ ] **Step 2: Open Draft PR and wait for exact-head CI**

Required CI evidence on the final head:
- Integration Reconciliation CI GREEN;
- Repository-wide Falsification Guard GREEN;
- P0-B/offline verification or equivalent repository full-regression workflow GREEN if triggered;
- Notion Access Policy Guard GREEN if triggered;
- exact full pytest/synthetic smoke counts recorded from logs.

- [ ] **Step 3: Attempt one manual V2 observation workflow run only if GitHub permits dispatching this branch workflow before merge**

Input: `confirm=RUN_V2_SHADOW_OBSERVATION`.
Expected artifact evidence:
- no secret/model credential use;
- `deep_dive_attempted_count == 0`;
- `actual_calls.deep_dive == 0`;
- `v2_selected_candidate_identity == null`;
- HN/arXiv statuses truthfully recorded;
- one JSON artifact exists.

If GitHub requires the workflow to exist on default branch before manual dispatch, record that platform limitation; do not merge to bypass the gate. First post-merge manual run becomes the workflow live proof.

- [ ] **Step 4: Inspect the artifact if a run occurred**

Verify it contains only public candidate identities/screening metadata plus source/config/status fields, and contains no raw exception text, manuscript content, Notion/note data, credentials or Production mutation evidence.

- [ ] **Step 5: Update Draft PR with final evidence**

Include changed-file inventory, RED/GREEN history, exact-head CI runs/counts, zero-model boundary, live proof outcome/platform limitation, and explicit statement that Daily/Fresh/Notion/note/Production authority are unchanged.

- [ ] **Step 6: Stop at merge readiness**

Do **not** mark merged or merge. Report MERGE READY only after all obtainable evidence is GREEN. Main integration requires a separate explicit **MERGE GO**.

---

## Self-Review Mapping

- Spec §§5/12/13 (manual trigger, credentials, Production isolation): Task 3 workflow contract + boundary tests.
- Spec §§6/7 (zero Deep Dive and leader semantics): Tasks 1–2.
- Spec §§8–10 (runner/output/report): Task 2.
- Spec §11 (source failure semantics): Task 2 tests and Task 5 live evidence.
- Spec §14 (TDD/boundaries/repository verification): Tasks 1–4.
- Spec §15 (live proof without weakening design): Task 5.
- Spec §16 acceptance criteria: every criterion is covered by Tasks 1–5; merge remains separately gated.

Type/interface review: `run_bounded_live_shadow` retains its existing required `deep_dive` callable and gains only the defaulted budget parameter. V2-003 supplies a local sentinel/no-op callable that must never execute because budget is `0`; no model provider dependency is introduced. Observation leader fields are copied only from the existing V2-001 `screening` summary, so private title/body content is not added by the runner.

Proportion review: the plan specifies interfaces, tests and verification gates but deliberately leaves function bodies and YAML details to implementation except where the spec fixes exact names/values.
