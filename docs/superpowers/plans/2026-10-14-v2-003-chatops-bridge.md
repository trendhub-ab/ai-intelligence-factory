# V2-003 ChatOps Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing AIIF ChatOps ONE-SHOT Bridge so ChatGPT can trigger V2-003 Manual Shadow Observation through Issue #71 without direct workflow-dispatch capability.

**Architecture:** Reuse the existing owner-only Issue #71 `issue_comment` bridge. Add one exact command to the Python authorizer and workflow allow-lists, then hard-map it to `v2-shadow-observation.yml` on `main` with the fixed confirmation token `RUN_V2_SHADOW_OBSERVATION`. Do not create a second bridge, do not execute V2 Python inside the bridge, and do not pass model/Notion/note/Production credentials or flags downstream.

**Tech Stack:** GitHub Actions YAML, Python 3.11, `unittest`/`pytest`, GitHub CLI/API through the existing `GH_PAT` bridge path.

**Spec:** `docs/superpowers/specs/2026-10-14-v2-003-chatops-bridge-design.md`

## Global Constraints

- Base main at plan creation: `43c5884ed101d845a8bf37248a89dccb9de61b03`.
- Canonical Chat command is exactly `/aiif run v2_shadow_observation`.
- Canonical Chat path is Issue #71 -> existing ChatOps ONE-SHOT Bridge -> `GH_PAT` dispatch -> `v2-shadow-observation.yml`.
- Issue must remain exactly `#71`; PR comments remain forbidden.
- Authorized login and actor remain exactly `trendhub-ab`.
- `github.run_attempt == 1` protection remains unchanged.
- Unknown or malformed commands fail closed.
- Dispatch ref is hard-coded to `main`.
- Dispatch confirmation is hard-coded to `RUN_V2_SHADOW_OBSERVATION`.
- `GH_PAT` is used only by the bridge to dispatch and is not forwarded to the V2 workflow.
- No Gemini/OpenAI/Google model, Notion, note, browser, Daily/Fresh/Rolling, arbitrary ref, arbitrary path, or arbitrary Deep Dive input is passed to V2.
- Existing `v2-shadow-observation.yml` remains zero-model, read-only, non-Production-authoritative.
- No new secret, control issue, bridge workflow, persistent queue, or scheduler is introduced.
- Existing security assertions and repository guards must not be weakened to obtain GREEN.
- Merge requires a separate explicit user `MERGE GO`.
- Post-merge acceptance requires a real Issue #71 ChatOps live proof; direct workflow dispatch does not satisfy that acceptance criterion.

## Review Focus

1. **Whitespace/case/extra-text drift:** only the exact V2 command may authorize; leading/trailing whitespace, newline, case variation, hyphen variation, and appended text must fail closed.
2. **Actor/control-surface drift:** wrong issue, wrong commenter, PR comments, or reruns must remain rejected.
3. **Credential creep:** the V2 dispatch case must not pass model, Notion, note, browser, or Production credentials/flags; `GH_PAT` remains bridge-local only.
4. **Target injection:** workflow name, ref, and confirmation must be constants; no user-controlled interpolation into those values.
5. **Bridge/target boundary erosion:** ChatOps must dispatch the V2 workflow rather than running `v2_shadow_observation.py` or `production_pipeline.py` directly.

---

### Task 1: Extend the fail-closed Python command authorizer

**Files:**
- Modify: `run202_chatops_control.py`
- Modify: `tests/test_run202_chatops_control.py`

**Interfaces:**
- Consumes: existing `authorize_event(event: dict[str, Any]) -> dict[str, Any]` contract.
- Produces: exact mapping `/aiif run v2_shadow_observation` -> mode `v2_shadow_observation` with empty `target_sync_id` and reason `authorized`.

- [ ] **Step 1: Write the failing exact-command authorization test**

Add `test_v2_shadow_observation_is_authorized` asserting:

```python
result = chatops.authorize_event(event(body="/aiif run v2_shadow_observation"))
self.assertEqual(
    result,
    {
        "authorized": True,
        "mode": "v2_shadow_observation",
        "target_sync_id": "",
        "reason": "authorized",
    },
)
```

- [ ] **Step 2: Write malformed-command rejection tests**

Add a dedicated test covering at least:

```text
/aiif run v2_shadow_observation<SPACE>
 /aiif run v2_shadow_observation
/aiif run v2_shadow_observation\n
/aiif run V2_shadow_observation
/aiif run v2-shadow-observation
/aiif run v2_shadow_observation please
```

`<SPACE>` denotes one literal trailing space in the rejected input and is documentation notation only.

Each must return `authorized == False`.

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```bash
python -m pytest -q tests/test_run202_chatops_control.py
```

Expected: the new positive V2 test fails because the command is not yet in `COMMAND_TO_MODE`; existing tests remain otherwise stable.

- [ ] **Step 4: Add the minimal command mapping**

Modify only `COMMAND_TO_MODE` in `run202_chatops_control.py`:

```python
"/aiif run v2_shadow_observation": "v2_shadow_observation",
```

Do not add a regex or free-form target parsing for this command.

- [ ] **Step 5: Run focused tests to verify GREEN**

Run:

```bash
python -m pytest -q tests/test_run202_chatops_control.py
```

Expected: PASS, including wrong issue, wrong actor, PR comment, whitespace, retired commands, and all existing ChatOps cases.

- [ ] **Step 6: Commit Task 1**

```bash
git add run202_chatops_control.py tests/test_run202_chatops_control.py
git commit -m "feat: authorize V2 shadow observation ChatOps command"
```

---

### Task 2: Route the authorized mode through the existing ONE-SHOT Bridge

**Files:**
- Modify: `.github/workflows/chatops-one-shot.yml`
- Modify: `tests/test_run202_chatops_control.py`

**Interfaces:**
- Consumes: mode `v2_shadow_observation` from Task 1.
- Produces: one hard-coded dispatch to `v2-shadow-observation.yml` on `main` with `confirm=RUN_V2_SHADOW_OBSERVATION`.

- [ ] **Step 1: Write workflow-contract RED tests**

Extend `Run202ChatOpsWorkflowContractTests` with assertions that require all of the following:

```text
/aiif run v2_shadow_observation
v2_shadow_observation
v2-shadow-observation.yml
"ref":"main"
"confirm":"RUN_V2_SHADOW_OBSERVATION"
```

Also assert the bridge contains no direct command that runs:

```text
python v2_shadow_observation.py
python production_pipeline.py
```

- [ ] **Step 2: Add credential-boundary assertions**

For the V2 route, assert the workflow does not introduce these environment names or payload fields:

```text
GEMINI_API_KEY
GOOGLE_API_KEY
OPENAI_API_KEY
NOTION_API_KEY
NOTION_TOKEN
NOTE_COOKIE
```

Preserve the existing assertions that dispatch uses:

```text
GH_TOKEN: ${{ secrets.GH_PAT }}
```

and never substitutes `github.token`.

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```bash
python -m pytest -q tests/test_run202_chatops_control.py
```

Expected: V2 workflow-route assertions fail because the bridge has no V2 mode or dispatch case yet.

- [ ] **Step 4: Add the exact workflow event allow-list entry**

In `.github/workflows/chatops-one-shot.yml`, add only:

```text
github.event.comment.body == '/aiif run v2_shadow_observation'
```

inside the existing owner/Issue #71/run-attempt predicate. Do not relax any surrounding predicate.

- [ ] **Step 5: Add the second mode allow-list entry**

Add `v2_shadow_observation` to the existing shell `case "$MODE" in` allow-list used after Python re-authorization.

- [ ] **Step 6: Add the constant dispatch case**

Add one case:

```bash
v2_shadow_observation)
  target='v2-shadow-observation.yml'
  payload='{"ref":"main","inputs":{"confirm":"RUN_V2_SHADOW_OBSERVATION"}}'
  ;;
```

Do not interpolate comment text, branch name, path, run ID, model name, or budget into the payload.

- [ ] **Step 7: Add safe summary metadata for the V2 mode**

In the existing `Record safe dispatch` step, record that for `v2_shadow_observation`:

```text
Gemini/Google/OpenAI model credentials passed: false
Notion/note writes authorized: false
Production authority changed: false
confirmation injected: RUN_V2_SHADOW_OBSERVATION
```

Do not print `GH_PAT` or any secret value.

- [ ] **Step 8: Run focused tests to verify GREEN**

Run:

```bash
python -m pytest -q tests/test_run202_chatops_control.py
```

Expected: PASS for both Python authorization and workflow contract checks.

- [ ] **Step 9: Commit Task 2**

```bash
git add .github/workflows/chatops-one-shot.yml tests/test_run202_chatops_control.py
git commit -m "ci: route V2 shadow observation through ChatOps bridge"
```

---

### Task 3: Prove repository isolation and synchronize governance metadata

**Files:**
- Modify only if required by guard output: `AI_Intelligence_Factory_最終仕様書.md`
- No new runtime modules expected.

**Interfaces:**
- Consumes: final Task 1-2 production surface.
- Produces: repository-wide proof that the bridge extension preserves existing Production and V2 isolation contracts.

- [ ] **Step 1: Run focused V2 + ChatOps safety tests**

Run:

```bash
python -m pytest -q \
  tests/test_run202_chatops_control.py \
  tests/test_v2_live_shadow_acquisition_budget.py \
  tests/test_v2_shadow_observation.py \
  tests/test_v2_shadow_observation_fixture.py \
  tests/test_v2_shadow_observation_boundary.py \
  tests/test_v2_shadow_observation_workflow.py
```

Expected: PASS.

- [ ] **Step 2: Run repository guards before changing canonical metadata**

Run:

```bash
python workflow_reference_guard.py
python repository_falsification_guard.py
python integration_stability_guard.py
python specification_freshness_guard.py
```

Expected: all semantic guards PASS; if canonical freshness fails only because the production fingerprint changed, capture the exact required fingerprint from guard output.

- [ ] **Step 3: Update only required canonical freshness metadata**

If and only if `specification_freshness_guard.py` requires it, update the Production Contract Fingerprint line in `AI_Intelligence_Factory_最終仕様書.md` to the exact guard-derived value. Do not rewrite unrelated specification text.

- [ ] **Step 4: Re-run freshness and falsification guards**

Run:

```bash
python specification_freshness_guard.py
python repository_falsification_guard.py
```

Expected: PASS without weakening any guard.

- [ ] **Step 5: Run full deterministic regression**

Run:

```bash
python -m pytest -q tests test_run360_gemini_retry_owner.py
```

Expected: full suite PASS; only pre-existing documented warnings are acceptable.

- [ ] **Step 6: Run synthetic Production smoke**

Run the same synthetic smoke command/environment used by `integration-reconciliation-ci.yml` so that the result includes:

```text
critical_failures=0
production_write_isolation=true
```

and all smoke cases pass.

- [ ] **Step 7: Run diff hygiene**

Run:

```bash
git diff --check main...HEAD
```

Expected: no output and exit 0.

- [ ] **Step 8: Commit governance-only metadata if changed**

If Task 3 changed the canonical fingerprint:

```bash
git add AI_Intelligence_Factory_最終仕様書.md
git commit -m "docs: sync V2 ChatOps bridge production fingerprint"
```

If no metadata change was needed, do not create an empty commit.

---

### Task 4: Open Draft PR, verify exact head, and stop at the merge gate

**Files:**
- No planned code changes.

**Interfaces:**
- Consumes: fully verified implementation branch.
- Produces: one Draft PR with exact-head CI evidence and a clear post-merge live-proof procedure.

- [ ] **Step 1: Compare branch with main**

Verify:

```text
merge base == approved base/main lineage
behind_by == 0
only planned files changed
```

If main advanced, inspect the intervening commits before continuing; do not silently merge or rebase over relevant changes.

- [ ] **Step 2: Open a Draft PR against `main`**

PR title:

```text
V2-003: ChatOps Bridge for Manual Shadow Observation
```

PR body must record:

- exact command `/aiif run v2_shadow_observation`
- Issue #71 owner-only path
- double authorization
- `GH_PAT` bridge-local dispatch
- target `v2-shadow-observation.yml`
- fixed confirmation token
- zero model / zero Notion-note write boundary
- intentional RED evidence
- exact-head GREEN evidence
- merge gate requiring explicit `MERGE GO`
- live proof deferred until after merge because the canonical path must execute from `main`

- [ ] **Step 3: Wait for exact-head CI and inspect final logs**

Required successful workflows:

```text
Integration Reconciliation CI
P0-B Offline Verification
Repository-wide Falsification Guard
Notion Access Policy Guard
Workflow Reference Guard
```

Record final test counts, guard status, synthetic smoke status, and `production_write_isolation` from the exact PR head.

- [ ] **Step 4: Confirm PR remains unmerged**

Verify:

```text
state=open
draft=true
merged=false
```

Stop. Do not merge without explicit user `MERGE GO`.

---

### Task 5: Post-merge ChatOps live proof

**Files:**
- No code changes planned.

**Interfaces:**
- Consumes: merged ChatOps route on `main`.
- Produces: operational evidence that ChatGPT can trigger V2-003 only through the approved workaround path.

**Precondition:** Task 5 begins only after the user explicitly authorizes and completes the merge.

- [ ] **Step 1: Confirm merged `main` contains the bridge route**

Verify the merge commit includes:

```text
/aiif run v2_shadow_observation
v2-shadow-observation.yml
RUN_V2_SHADOW_OBSERVATION
```

- [ ] **Step 2: Trigger from ChatGPT through Issue #71**

Use the GitHub connector to add exactly this owner comment to Issue #71:

```text
/aiif run v2_shadow_observation
```

Do not use direct workflow dispatch as a substitute.

- [ ] **Step 3: Verify the bridge run**

Locate the resulting `AIIF ChatOps ONE-SHOT Bridge` run and verify:

```text
event == issue_comment
authorization succeeds
requested mode == v2_shadow_observation
dispatch target == v2-shadow-observation.yml on main
```

- [ ] **Step 4: Verify the downstream V2 run**

Locate the downstream `V2 Manual Shadow Observation [ZERO MODEL]` run and verify completion under the V2-003 contract.

- [ ] **Step 5: Verify the artifact**

Confirm exactly one observation artifact is produced and inspect its JSON for:

```text
deep_dive_attempted_count == 0
actual_calls.deep_dive == 0
v2_selected_candidate_identity == null
pre_deep_dive_leader == object-or-null
bounded source/status metadata present
```

- [ ] **Step 6: Verify no Production mutation**

Confirm no Daily/Fresh/Rolling/note/Notion Production workflow or write path was triggered by this live proof.

- [ ] **Step 7: Record proof outcome**

Add the bridge run ID, downstream V2 run ID, artifact name, and pass/fail summary to the merged PR or designated audit location without copying secrets or raw private content.

Acceptance for Task 5 is **FAILED** if only a direct UI/manual V2 dispatch is demonstrated, or if the bridge succeeds but the downstream run cannot be identified and explained.
