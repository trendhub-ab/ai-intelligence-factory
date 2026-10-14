# V2-003 ChatOps Bridge Design

Status: `AWAITING_USER_REVIEW`
Date: 2026-10-14
Base main: `43c5884ed101d845a8bf37248a89dccb9de61b03`
Branch: `design/v2-003-chatops-bridge`

## 1. Purpose

V2-003 Manual Shadow Observation is now on `main`, but ChatGPT cannot directly invoke GitHub Actions `workflow_dispatch` through the current GitHub connector.

AIIF already has a proven workaround: the existing owner-only `AIIF ChatOps ONE-SHOT Bridge` receives an exact command posted to dedicated control Issue #71, re-authorizes it fail-closed, then uses `GH_PAT` to dispatch an allow-listed manual workflow.

This design extends that existing bridge with one V2 command instead of creating a new bridge or coupling Chat directly to Production execution.

Canonical operator path:

```text
ChatGPT
  |
  | add exact owner comment
  v
GitHub Issue #71
  |
  | issue_comment.created
  v
.github/workflows/chatops-one-shot.yml
  |
  | first authorization in workflow event predicate
  v
run202_chatops_control.py
  |
  | second fail-closed authorization
  v
GH_PAT workflow dispatch
  |
  v
.github/workflows/v2-shadow-observation.yml
  |
  | confirm=RUN_V2_SHADOW_OBSERVATION
  v
V2 bounded live zero-model observation
  |
  v
short-lived JSON artifact
```

Invariant:

> **ChatはIssue #71を経由する。Bridgeが認証してV2を発火する。V2は観測するだけで、V1 Production authorityには触れない。**

## 2. Fixed platform constraint

The current ChatGPT GitHub connector does not expose a workflow-dispatch action. This is treated as a fixed operator constraint for AIIF V2 design.

Therefore:

- Chat-originated execution MUST NOT assume direct `workflow_dispatch`.
- The canonical Chat path MUST go through a connector-supported GitHub mutation.
- The chosen mutation is an exact comment on the existing dedicated control Issue #71.
- Human GitHub UI `workflow_dispatch` may remain available as an emergency/manual fallback, but it is not the canonical Chat execution path.

## 3. Existing proven mechanism to reuse

Existing files on `main`:

- `.github/workflows/chatops-one-shot.yml`
- `run202_chatops_control.py`
- `tests/test_run202_chatops_control.py`
- `.github/workflows/v2-shadow-observation.yml`

Existing ChatOps security properties that MUST remain unchanged:

1. Trigger is `issue_comment.created` only.
2. Dedicated control issue is exactly `#71`.
3. Pull request comments are rejected.
4. Comment author must be exactly `trendhub-ab`.
5. `github.actor` must be exactly `trendhub-ab`.
6. `github.run_attempt == 1`; manual rerun is rejected.
7. Command matching is exact/fail-closed.
8. Python authorization runs after workflow-level authorization.
9. Unknown commands fail closed.
10. Bridge does not run Production logic itself.
11. Dispatch uses `GH_PAT`, not `github.token`, so downstream workflow events remain chainable.
12. Missing `GH_PAT` fails closed.

No existing command semantics may be relaxed to add V2 support.

## 4. New command contract

Exactly one new command is added:

```text
/aiif run v2_shadow_observation
```

Authorized mode:

```text
v2_shadow_observation
```

The command MUST be accepted only as an exact full-string match.

The following MUST fail closed:

```text
/aiif run v2_shadow_observation 
 /aiif run v2_shadow_observation
/aiif run v2_shadow_observation\n
/aiif run V2_shadow_observation
/aiif run v2-shadow-observation
/aiif run v2_shadow_observation please
/aiif run v2_shadow_observation anything
```

No free-form arguments, branch names, refs, paths, model names, URLs, or IDs are accepted for this command.

## 5. Dispatch contract

For mode `v2_shadow_observation`, the bridge dispatches exactly:

```text
workflow: .github/workflows/v2-shadow-observation.yml
ref: main
input:
  confirm: RUN_V2_SHADOW_OBSERVATION
```

Equivalent payload:

```json
{
  "ref": "main",
  "inputs": {
    "confirm": "RUN_V2_SHADOW_OBSERVATION"
  }
}
```

The bridge MUST NOT pass:

- Gemini API credentials
- OpenAI credentials
- Google model credentials
- Notion credentials
- note credentials/cookies
- browser credentials
- Production mode flags
- Daily/Fresh/Rolling flags
- arbitrary refs or branches
- arbitrary Deep Dive budgets

`GH_PAT` exists only in the bridge job as dispatch authorization. It is not forwarded to the V2 target workflow.

## 6. Target workflow remains V2-003 zero-model observation

The existing `.github/workflows/v2-shadow-observation.yml` remains the execution owner.

It continues to require:

```text
confirm == RUN_V2_SHADOW_OBSERVATION
```

It continues to enforce:

- `permissions: contents: read`
- no schedule trigger
- no push trigger
- no Production workflow invocation
- zero Deep Dive calls
- zero Gemini/OpenAI calls
- zero Notion/note writes
- bounded public GET acquisition only
- `v2_selected_candidate_identity == null`
- diagnostic `pre_deep_dive_leader` only
- one short-lived observation JSON artifact

The ChatOps bridge does not duplicate or bypass those safety checks.

## 7. Files expected to change during implementation

Primary changes:

1. `run202_chatops_control.py`
   - add exact command mapping:
     - `/aiif run v2_shadow_observation` -> `v2_shadow_observation`

2. `.github/workflows/chatops-one-shot.yml`
   - add exact event predicate allow-list entry
   - add `v2_shadow_observation` to the second mode allow-list
   - add one dispatch case targeting `v2-shadow-observation.yml`
   - inject exact `RUN_V2_SHADOW_OBSERVATION` confirmation
   - record safe summary metadata that explicitly states zero-model / no Production writes

3. `tests/test_run202_chatops_control.py`
   - add authorization positive case
   - add malformed-command rejection cases
   - verify exact target workflow
   - verify exact confirmation payload
   - verify no model/Notion credentials are introduced
   - verify existing commands still behave unchanged

Conditional governance changes only if existing guards require them:

4. `AI_Intelligence_Factory_最終仕様書.md`
   - update canonical Production Contract Fingerprint only if computed Production surface changes require it
   - do not rewrite unrelated specification text

No new bridge workflow is planned.
No new Python execution subsystem is planned.
No new secrets are planned.

## 8. Security model

### Layer 1: GitHub event predicate

The existing workflow-level `if` remains the first gate and adds only one exact allowed command.

Required V2 predicate conditions remain conjunctive with the existing owner/control issue restrictions.

### Layer 2: Python authorization

`run202_chatops_control.authorize_event()` independently validates:

- issue shape
- issue number 71
- non-PR issue
- exact authorized login
- exact command body

It returns `authorized=true` only for the exact new command.

### Layer 3: mode allow-list

The shell case statement accepts `v2_shadow_observation` explicitly and rejects unknown values.

### Layer 4: exact downstream target

The V2 mode maps to one constant target workflow and one constant payload. User-controlled strings are not interpolated into workflow path, ref, or input values.

### Layer 5: target workflow confirmation

The V2 workflow again requires the exact typed confirmation token before execution.

### Layer 6: V2 execution isolation

V2-003 remains read-only / zero-model and has no Production authority.

## 9. Failure semantics

### Unauthorized or malformed comment

- Bridge job is not authorized or Python authorization returns false.
- No downstream workflow is dispatched.
- No fallback command interpretation occurs.

### Missing `GH_PAT`

- Bridge fails closed.
- No downstream execution occurs.
- Do not substitute `github.token`.

### Dispatch API failure

- Bridge fails.
- No retry loop is added in this scope.
- Operator may issue a fresh exact command after the failure is understood.

### V2 workflow failure

- Failure remains inside the V2 workflow/run.
- Bridge does not reinterpret the result or trigger Production fallback.

### Source outage inside V2

- Existing V2 semantics remain authoritative: partial/all source outage is represented as a bounded fail-closed observation where applicable, not as a reason to invoke Production.

## 10. Concurrency and duplicate behavior

The existing ChatOps bridge concurrency group remains unchanged:

```text
aiif-chatops-one-shot-control
```

`cancel-in-progress: false` remains unchanged.

No durable idempotency ledger is added for this V2 command. The operator contract is one exact comment per requested observation.

A second exact comment is a second explicit request and may produce a second V2 run. This is acceptable for zero-model, read-only observation and keeps scope minimal.

## 11. Cost contract

Per V2 observation request:

- Gemini: 0 calls
- OpenAI: 0 calls
- other paid model providers: 0 calls
- Notion: 0 writes
- note: 0 writes
- browser automation: 0
- new secrets: 0
- GitHub API: one owner comment event plus one workflow dispatch through existing GH_PAT
- GitHub Actions: bridge job + bounded V2 observation job

This is deliberately lower-risk and lower-maintenance than creating another bridge subsystem.

## 12. TDD strategy

Implementation MUST start RED.

### Authorization RED tests

Add tests that expect:

1. exact `/aiif run v2_shadow_observation` is authorized
2. returned mode is exactly `v2_shadow_observation`
3. trailing whitespace is rejected
4. leading whitespace is rejected
5. newline is rejected
6. case variation is rejected
7. extra text is rejected
8. wrong issue remains rejected
9. wrong actor remains rejected
10. PR comment remains rejected

Before implementation, the positive test MUST fail because the command is not yet allow-listed.

### Workflow contract RED tests

Add tests that require:

1. exact command exists in workflow event allow-list
2. `v2_shadow_observation` exists in second shell mode allow-list
3. target is exactly `v2-shadow-observation.yml`
4. payload ref is exactly `main`
5. payload confirmation is exactly `RUN_V2_SHADOW_OBSERVATION`
6. V2 dispatch case does not introduce Gemini/OpenAI/Google/Notion credentials
7. bridge still uses `GH_PAT`
8. bridge still rejects absent `GH_PAT`
9. bridge still does not run `v2_shadow_observation.py` directly
10. bridge still does not run `production_pipeline.py` directly

Before implementation, the new V2-specific contract tests MUST fail for the missing route.

### Regression verification

After focused GREEN:

- full pytest
- existing ChatOps adversarial tests
- Workflow Reference Guard
- Repository-wide Falsification Guard
- Integration Stability Guard
- canonical freshness/fingerprint guard if applicable
- `git diff --check`
- existing synthetic Production smoke, if required by the standard integration workflow

Existing security assertions must not be weakened to obtain GREEN.

## 13. Live proof after merge

The live proof MUST itself use the workaround path; direct workflow dispatch is not acceptable as proof of the Chat execution route.

Exact proof sequence:

1. Confirm merged `main` contains the approved bridge route.
2. From ChatGPT, use the GitHub connector to add exactly this comment to Issue #71:

   ```text
   /aiif run v2_shadow_observation
   ```

3. Observe the resulting `AIIF ChatOps ONE-SHOT Bridge` run.
4. Verify its authorization job succeeds.
5. Verify its recorded dispatch target is `v2-shadow-observation.yml` on `main`.
6. Locate the downstream `V2 Manual Shadow Observation [ZERO MODEL]` run.
7. Verify the downstream run completes under the V2-003 safety contract.
8. Verify one observation artifact exists.
9. Inspect artifact/report metadata for:
   - zero Deep Dive attempts
   - zero Deep Dive actual calls
   - no selected V2 winner
   - diagnostic pre-DD leader or null
   - bounded source results
10. Verify no Production mutation was triggered.

If the bridge run succeeds but downstream dispatch cannot be found, live proof is FAILED until the chain is explained.

If a direct UI/manual dispatch is used instead, it may prove the target workflow itself but it does NOT satisfy the ChatOps Bridge live-proof acceptance criterion.

## 14. Acceptance criteria

Implementation is merge-ready only when all are true:

1. Exact Chat command is `/aiif run v2_shadow_observation`.
2. Canonical Chat execution path is Issue #71 -> existing ChatOps Bridge -> GH_PAT dispatch -> V2 workflow.
3. No new bridge workflow or new secret is introduced.
4. Existing owner-only Issue #71 authorization remains intact.
5. Existing PR-comment rejection remains intact.
6. Existing `run_attempt == 1` protection remains intact.
7. Python re-authorization remains fail-closed.
8. Unknown/malformed V2 commands are rejected.
9. V2 target is hard-coded to `v2-shadow-observation.yml` on `main`.
10. V2 confirmation is hard-coded to `RUN_V2_SHADOW_OBSERVATION`.
11. Bridge does not execute V2 Python directly.
12. Bridge does not forward model, Notion, note, or Production credentials/flags to V2.
13. Existing V2-003 zero-model/read-only guarantees remain unchanged.
14. Focused TDD shows intentional RED before implementation and GREEN after.
15. Full regression and repository guards are GREEN on exact final head.
16. Main merge occurs only after explicit user `MERGE GO`.
17. Post-merge live proof is performed by posting the exact command to Issue #71 from ChatGPT.
18. The live proof demonstrates both the bridge run and downstream V2 run, not merely the target workflow in isolation.

## 15. Explicitly deferred

Not in this change:

- V2 real Deep Dive/model calls
- scheduled V2 execution
- new ChatOps control issue
- replacement of Issue #71
- new secrets or GitHub App
- arbitrary workflow dispatch from Chat
- generic command parser/ref selector
- branch/ref input from Chat
- persistent V2 observation history
- V2 Production authority
- Daily/Fresh/Rolling integration
- V1 retirement

## 16. Rationale

Three approaches were considered:

### A. Extend the existing ChatOps ONE-SHOT Bridge — selected

Advantages:

- already implemented and operationally proven
- directly callable from the available ChatGPT GitHub connector
- owner/control-issue restrictions already hardened
- double authorization already exists
- GH_PAT dispatch behavior already established
- smallest code and maintenance surface

### B. Create a V2-specific issue-comment bridge — rejected

This duplicates authorization, secrets handling, workflow dispatch logic, tests, and operational ownership without adding meaningful safety.

### C. Execute V2 directly inside `chatops-one-shot.yml` — rejected

This couples authorization and execution, weakens component boundaries, bypasses the target workflow confirmation contract, and makes future V2 evolution harder to reason about.

Therefore the selected design is a narrow allow-list extension of the existing proven bridge.
