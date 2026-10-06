# P0-B Strong-Zero Retry Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely authorize exactly one new private-note draft creation attempt after a strong-zero reconciliation, preserve the complete durable audit history, complete B01 to `QUEUE_CONFIRMED`, and prove that ordinary retries cannot create a duplicate.

**Architecture:** Keep one durable GCS object per logical delivery and retain the existing logical/revision/operation identity. Add a dedicated `authorize_reconciled_retry()` operation that is separate from generic state transitions and uses the existing single-object generation CAS; only its CAS winner receives creation authority. Reuse the existing browser creation/verification/queue-confirmation path through a factored runtime helper, and keep ordinary `begin_or_load()` behavior unchanged.

**Tech Stack:** Python 3.11, pytest, SQLite parity tests, Google Cloud Storage generation preconditions, GitHub Actions hosted `ubuntu-latest`, Workload Identity Federation, Playwright/Chromium, Notion exact readback.

**Spec:** `docs/superpowers/specs/2026-10-06-p0-b-strong-zero-retry-authority-design.md`

## Global Constraints

- Production durable authority remains the private GCS object ledger; SQLite is test/interface parity only.
- Do not add `MANUAL_RECONCILIATION_REQUIRED -> CREATE_INTENT_RECORDED` to generic `_ALLOWED_TRANSITIONS`.
- Do not delete/reset the durable GCS object, reset `state_version`, or clear event history.
- Normal `begin_or_load()` must never restore creation authority for an existing operation.
- A stable draft identity must be durably recorded before Notion queue mutation.
- Ambiguous browser creation must fail closed to `CREATION_UNKNOWN`; there is no automatic second create.
- Queue completion requires exact Notion readback; PATCH success alone is insufficient.
- No PC, self-hosted runner, GCE runner, OS username, UID/GID, systemd, or home-directory contract.
- Retry/recovery path uses zero Gemini/OpenAI/model calls and never publishes a note.
- Keep sensitive sync IDs, draft IDs, titles, URLs, and evidence payloads out of public logs; emit only safe status/count/digest summaries.
- Do not merge to `main` without explicit `MERGE GO`.
- Do not create the live trigger marker until all offline verification is GREEN.

## Review Focus

1. **Stale or forged strong-zero evidence:** only an exact durable `creation_absence_confirmed_strong_zero:<64 lowercase hex>` category plus a fresh current `strong_zero` census may lead to authorization; Task 1 and Task 4 pin this.
2. **Two workers racing to retry:** at most one GCS generation-CAS winner may receive `creation_authorized=true`; Task 2 pins both winner and loser behavior.
3. **Crash after retry CAS but before browser mutation:** lease expiry alone must not restore authority; only fresh-evidence explicit reconciliation may return the consumed intent to `MANUAL_RECONCILIATION_REQUIRED`; Task 4 pins this.
4. **Draft identity becomes durable before a later failure:** once `draft_id` exists, no recovery path may authorize creation; the runtime must continue only against that draft; Task 3 pins this.
5. **Notion PATCH succeeds but readback is ambiguous/wrong:** state must not become `QUEUE_CONFIRMED`, and draft recreation must remain forbidden; Task 3 and Task 6 pin this.

---

### Task 1: Shared Strong-Zero Evidence Contract and Ledger API

**Files:**
- Create: `note_delivery_strong_zero.py`
- Modify: `note_delivery_ledger.py`
- Modify: `run_p0b_strong_zero_reconciliation.py`
- Create: `tests/test_note_delivery_strong_zero.py`
- Modify: `tests/test_note_delivery_ledger.py`
- Test: `tests/test_p0b_strong_zero_reconciliation.py`

**Interfaces:**
- Consumes: existing census result schema and `DeliverySnapshot`, `DeliveryRecord`, `IntentDecision`.
- Produces:
  - `validate_strong_zero_census(census: Mapping[str, Any]) -> dict[str, Any]`
  - `strong_zero_evidence_digest(census: Mapping[str, Any]) -> str`
  - `parse_strong_zero_evidence_category(category: str) -> str`
  - `DeliveryLedger.authorize_reconciled_retry(snapshot: DeliverySnapshot, *, run_correlation_id: str, expected_version: int) -> IntentDecision`
  - `SQLiteDeliveryLedger.authorize_reconciled_retry(...) -> IntentDecision`

- [ ] **Step 1: Write failing pure evidence tests**

Add tests asserting:
- the existing nine-key census schema with authenticated `strong_zero`, positive observable private-card count, zero exact target, zero suspicious blank, zero unreadable, zero mutation, and zero model calls validates;
- any missing/extra census key fails;
- non-`strong_zero`, unauthenticated, zero observable cards, target count > 0, blank/unreadable > 0, mutation > 0, or model use fails;
- `parse_strong_zero_evidence_category()` accepts only `creation_absence_confirmed_strong_zero:` followed by exactly 64 lowercase hex characters and returns only the digest;
- uppercase, short, empty, extra-suffix, or wrong-prefix evidence fails.

- [ ] **Step 2: Run the new evidence tests and verify RED**

Run: `python -m pytest -q tests/test_note_delivery_strong_zero.py`

Expected: FAIL because `note_delivery_strong_zero.py` / public helpers do not exist.

- [ ] **Step 3: Implement the pure evidence module and move phase-one reconciliation onto it**

Keep the census schema and digest algorithm byte-for-byte compatible with the existing phase-one behavior. `run_p0b_strong_zero_reconciliation.py` must call the shared public helpers rather than maintain a second validation contract.

- [ ] **Step 4: Write failing SQLite retry-authority tests**

In `tests/test_note_delivery_ledger.py`, add tests that prepare an existing operation in `MANUAL_RECONCILIATION_REQUIRED` with a valid durable strong-zero evidence category and assert:
- snapshot equality + no `draft_id` + exact expected version authorizes once;
- returned record is `CREATE_INTENT_RECORDED`, `state_version` increments by one, `attempt_count` increments by one, owner correlation changes to the retry run, owner expiry is populated, prior snapshot is unchanged, and `creation_authorized=True`;
- malformed evidence, snapshot drift, existing `draft_id`, wrong state, or stale `expected_version` fails closed;
- a second ordinary `begin_or_load()` returns `creation_authorized=False`;
- generic `_ALLOWED_TRANSITIONS` still does not contain `MANUAL_RECONCILIATION_REQUIRED -> CREATE_INTENT_RECORDED`.

- [ ] **Step 5: Run the focused ledger tests and verify RED**

Run: `python -m pytest -q tests/test_note_delivery_ledger.py -k 'reconciled_retry or manual_reconciliation'`

Expected: FAIL because the dedicated ledger API does not exist.

- [ ] **Step 6: Implement SQLite parity and protocol signature**

Implement `authorize_reconciled_retry()` as a dedicated SQLite transaction, not via generic `_transition()`. It must re-read the active logical record inside the transaction, validate exact state/version/snapshot/draft/evidence, increment state/attempt metadata, preserve `conflict_category` strong-zero evidence, and append `strong_zero_retry_authorized:<digest>` to `delivery_events` atomically.

- [ ] **Step 7: Run focused and phase-one regression tests**

Run:
`python -m pytest -q tests/test_note_delivery_strong_zero.py tests/test_note_delivery_ledger.py tests/test_p0b_strong_zero_reconciliation.py`

Expected: PASS, with the phase-one reconciliation behavior unchanged.

- [ ] **Step 8: Commit**

```bash
git add note_delivery_strong_zero.py note_delivery_ledger.py run_p0b_strong_zero_reconciliation.py tests/test_note_delivery_strong_zero.py tests/test_note_delivery_ledger.py tests/test_p0b_strong_zero_reconciliation.py
git commit -m "feat: add dedicated strong-zero retry authority contract"
```

### Task 2: GCS Generation-CAS Retry Authorization

**Files:**
- Modify: `note_delivery_gcs.py`
- Modify: `tests/test_note_delivery_gcs.py`

**Interfaces:**
- Consumes: Task 1 `DeliveryLedger.authorize_reconciled_retry(...)`, `parse_strong_zero_evidence_category()`.
- Produces: `GCSDeliveryLedger.authorize_reconciled_retry(snapshot: DeliverySnapshot, *, run_correlation_id: str, expected_version: int) -> IntentDecision` using the existing record object's observed generation.

- [ ] **Step 1: Write failing GCS authorization and concurrency tests**

Add tests asserting:
- eligible manual-reconciliation record is rewritten with `if_generation_match=<observed generation>` and returns `creation_authorized=True`;
- state/version/attempt/owner lease/event are updated atomically and old events remain in order;
- stale `state_version`, snapshot drift, draft ID, malformed evidence, or wrong state yields no authority;
- forced stale generation raises/returns a concurrency failure without an unconditional overwrite;
- two concurrent callers against the same generation yield exactly one authorization winner and at most one `strong_zero_retry_authorized:` event.

- [ ] **Step 2: Run focused GCS tests and verify RED**

Run: `python -m pytest -q tests/test_note_delivery_gcs.py -k 'reconciled_retry or retry_authority or concurrent'`

Expected: FAIL because the GCS dedicated method is absent.

- [ ] **Step 3: Implement dedicated single-object CAS**

Read the record by logical key, validate all Task 1 conditions, derive the existing evidence digest from `conflict_category`, create the updated record/event in memory, and call existing `_write(..., expected_generation=generation)`. Do not add the transition to `_ALLOWED_TRANSITIONS` and do not create a second GCS object/pointer.

- [ ] **Step 4: Run GCS and ledger parity tests**

Run: `python -m pytest -q tests/test_note_delivery_gcs.py tests/test_note_delivery_ledger.py`

Expected: PASS; fake GCS upload conditions show no unconditional overwrite.

- [ ] **Step 5: Commit**

```bash
git add note_delivery_gcs.py tests/test_note_delivery_gcs.py
git commit -m "feat: authorize strong-zero retry with GCS generation CAS"
```

### Task 3: Reuse the Existing Creation Pipeline Without Opening a Second Create Path

**Files:**
- Modify: `note_delivery_runtime.py`
- Modify: `tests/test_note_delivery_runtime.py`

**Interfaces:**
- Consumes: `DeliveryLedger.authorize_reconciled_retry(...)` from Tasks 1-2.
- Produces:
  - `_execute_authorized_creation(base: Any, ledger: DeliveryLedger, prepared: PreparedDelivery, record: DeliveryRecord) -> DeliveryRecord`
  - `create_reconciled_retry(base: Any, ledger: DeliveryLedger, prepared: PreparedDelivery, *, run_correlation_id: str, expected_version: int) -> DeliveryRecord`
- Ordinary `create_or_resume_delivery(...)` remains its public contract and delegates its already-authorized create branch to `_execute_authorized_creation()`.

- [ ] **Step 1: Write failing runtime factoring/retry tests**

Add tests asserting:
- normal first creation still creates exactly once and reaches the same verified/queue behavior;
- `create_reconciled_retry()` creates only when the dedicated ledger call returns `creation_authorized=True`;
- a rejected/stale/concurrent authorization performs zero browser mutation;
- after one successful retry authorization, a second ordinary `create_or_resume_delivery()` does not create again;
- browser exception before durable draft ID moves the consumed retry intent to `CREATION_UNKNOWN` and no automatic second create occurs;
- once stable draft ID is recorded, subsequent failure/retry never calls create again;
- queue PATCH/readback mismatch never reaches `QUEUE_CONFIRMED` and never triggers recreation.

- [ ] **Step 2: Run focused runtime tests and verify RED**

Run: `python -m pytest -q tests/test_note_delivery_runtime.py -k 'reconciled_retry or create_or_resume or creation_unknown or queue'`

Expected: FAIL because the dedicated retry runtime function/factored executor is absent.

- [ ] **Step 3: Extract the existing post-authorization create body into `_execute_authorized_creation()`**

Move, do not redesign, the existing revalidate → storage-state decode → browser create → stable-ID callback → canonical verify → queue PATCH/readback logic. Preserve all existing exception-to-ledger behavior.

- [ ] **Step 4: Add `create_reconciled_retry()`**

Call `ledger.authorize_reconciled_retry()` once. If not authorized, return the durable record without browser mutation. If authorized, pass that exact returned record to `_execute_authorized_creation()`; do not call `begin_or_load()` in between.

- [ ] **Step 5: Run runtime plus existing P0-B tests**

Run: `python -m pytest -q tests/test_note_delivery_runtime.py tests/test_note_delivery_ledger.py tests/test_note_delivery_gcs.py`

Expected: PASS and existing ordinary creation semantics unchanged.

- [ ] **Step 6: Commit**

```bash
git add note_delivery_runtime.py tests/test_note_delivery_runtime.py
git commit -m "refactor: reuse one fail-closed creation executor for reconciled retry"
```

### Task 4: Fresh-Evidence Retry Orchestrator and Expired-Intent Reconciliation

**Files:**
- Create: `run_p0b_strong_zero_retry.py`
- Create: `tests/test_p0b_strong_zero_retry.py`
- Modify: `run_p0b_strong_zero_reconciliation.py` only if shared helper imports require compatibility cleanup.

**Interfaces:**
- Consumes: Task 1 strong-zero helpers; Task 3 `create_reconciled_retry()`.
- Produces:
  - `run_reconciled_retry(base: Any, ledger: DeliveryLedger, *, sync_id: str, note_target: str, current_snapshot: DeliverySnapshot, census: Mapping[str, Any], run_correlation_id: str, expected_version: int) -> DeliveryRecord`
  - `reconcile_expired_retry_intent(ledger: DeliveryLedger, *, sync_id: str, note_target: str, current_snapshot: DeliverySnapshot, census: Mapping[str, Any], now: datetime | None = None) -> DeliveryRecord`

- [ ] **Step 1: Write failing orchestrator tests**

Assert `run_reconciled_retry()` refuses to call runtime authorization unless fresh census is valid `strong_zero`, current snapshot equals the durable snapshot, active state is exactly `MANUAL_RECONCILIATION_REQUIRED`, draft ID is absent, and durable strong-zero evidence parses correctly.

- [ ] **Step 2: Write failing expired-intent tests**

Prepare a retry-authorized `CREATE_INTENT_RECORDED` record and assert:
- lease expiry by itself does not make `begin_or_load()` authorize creation;
- before expiry, explicit reconciliation is rejected;
- after expiry, fresh `strong_zero` + exact snapshot + no draft ID transitions only to `MANUAL_RECONCILIATION_REQUIRED` with a new strong-zero digest;
- expired-intent reconciliation returns no creation authority;
- non-strong-zero/new draft ID/snapshot drift blocks the reconciliation.

- [ ] **Step 3: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_p0b_strong_zero_retry.py`

Expected: FAIL because the orchestrator does not exist.

- [ ] **Step 4: Implement the bounded orchestrator**

Keep all census/snapshot checks before authorization. For expired-intent reconciliation, require the existing retry record to be identifiable by valid retained strong-zero evidence plus expired `owner_expires_at`; use existing `record_blocked(... MANUAL_RECONCILIATION_REQUIRED ...)` only after fresh evidence validates. Do not add an automatic timer or scheduled workflow.

- [ ] **Step 5: Run focused recovery tests**

Run: `python -m pytest -q tests/test_p0b_strong_zero_retry.py tests/test_p0b_strong_zero_reconciliation.py`

Expected: PASS, with zero model/browser mutation in expired-intent reconciliation tests.

- [ ] **Step 6: Commit**

```bash
git add run_p0b_strong_zero_retry.py tests/test_p0b_strong_zero_retry.py run_p0b_strong_zero_reconciliation.py
git commit -m "feat: orchestrate fresh-evidence strong-zero retry"
```

### Task 5: Hosted One-Shot Retry Workflow Contract

**Files:**
- Create: `.github/workflows/p0b-strong-zero-retry-live.yml`
- Create: `tests/test_p0b_strong_zero_retry_live_workflow.py`
- Modify: `.github/workflows/p0b-offline-verification.yml` to include the new module/workflow in its path filter if needed.
- Do **not** create/update: `ops/p0b-strong-zero-retry.trigger` until Task 6.

**Interfaces:**
- Consumes: existing WIF variables/secrets, `run199_note_vm_preflight.py` candidate selection, hosted census `run_p0b_hosted_private_draft_census.py`, Task 4 orchestrator, existing note browser/queue contracts.
- Produces: a path-gated hosted one-shot workflow that can execute the approved B01 retry exactly once after offline GREEN.

- [ ] **Step 1: Write failing static workflow contract tests**

Assert the workflow:
- runs only on `ubuntu-latest`/hosted Linux and contains no `self-hosted`, GCE, OS-user, UID/GID, systemd, or home-directory runner dependency;
- triggers only when `ops/p0b-strong-zero-retry.trigger` changes on the explicit ops/implementation branch;
- installs `pytest requests google-cloud-storage playwright pillow` and Chromium before runtime use;
- authenticates to GCS with existing GitHub OIDC/WIF variables;
- selects one exact Ready candidate without model calls;
- requires current durable state `MANUAL_RECONCILIATION_REQUIRED` before authorization;
- runs a fresh hosted strong-zero census before authorization;
- rebuilds and compares immutable snapshot before authorization;
- invokes the retry orchestrator once;
- verifies durable `QUEUE_CONFIRMED`, non-empty stable draft ID, canonical verification hash, and queue receipt digest after success;
- performs a final ordinary retry proof that results in zero new browser create calls and keeps the same draft identity;
- never invokes note publish or a model API.

- [ ] **Step 2: Run workflow contract test and verify RED**

Run: `python -m pytest -q tests/test_p0b_strong_zero_retry_live_workflow.py`

Expected: FAIL because the workflow does not exist.

- [ ] **Step 3: Implement the workflow without touching the trigger marker**

Use the same secret masking and ephemeral-file cleanup conventions as `p0b-strong-zero-reconciliation-live.yml` and `note-create-draft.yml`. Keep the create/verify/queue sequence in one bounded job after the CAS winner obtains authority; do not dispatch a second ordinary create workflow that could lose the in-memory authorization result.

- [ ] **Step 4: Run workflow/static regressions**

Run:
`python -m pytest -q tests/test_p0b_strong_zero_retry_live_workflow.py tests/test_p0b_strong_zero_retry.py`

Then run:
`python workflow_reference_guard.py`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/p0b-strong-zero-retry-live.yml .github/workflows/p0b-offline-verification.yml tests/test_p0b_strong_zero_retry_live_workflow.py
git commit -m "ci: add hosted one-shot strong-zero retry proof"
```

### Task 6: Full Offline Verification, One B01 Live Proof, and Duplicate-Block Proof

**Files:**
- Modify only after all offline GREEN: `ops/p0b-strong-zero-retry.trigger`
- No `main` changes.

**Interfaces:**
- Consumes: Tasks 1-5 complete implementation.
- Produces: fresh evidence that B01 reaches `QUEUE_CONFIRMED` exactly once and a subsequent ordinary retry creates zero additional drafts.

- [ ] **Step 1: Run focused retry-authority suite**

Run:
`python -m pytest -q tests/test_note_delivery_strong_zero.py tests/test_note_delivery_ledger.py tests/test_note_delivery_gcs.py tests/test_note_delivery_runtime.py tests/test_p0b_strong_zero_reconciliation.py tests/test_p0b_strong_zero_retry.py tests/test_p0b_strong_zero_retry_live_workflow.py`

Expected: PASS with zero failures.

- [ ] **Step 2: Run full repository pytest**

Run: `python -m pytest tests -q`

Expected: zero failures.

- [ ] **Step 3: Run repository guards exactly as CI does**

Run:
```bash
python workflow_reference_guard.py
python repository_falsification_guard.py
python integration_stability_guard.py
git diff --check origin/main...HEAD
```

Expected: all commands exit 0.

- [ ] **Step 4: Confirm no live retry workflow is already running and re-read durable state**

Read-only requirements immediately before the trigger:
- exactly one target Ready candidate;
- durable state `MANUAL_RECONCILIATION_REQUIRED`;
- no stable draft ID;
- immutable snapshot matches;
- fresh census returns authenticated `strong_zero`, target 0, blank 0, unreadable 0, mutation 0, model calls 0.

If any condition differs, stop; do not trigger.

- [ ] **Step 5: Create/update the one-shot marker exactly once**

Create or update `ops/p0b-strong-zero-retry.trigger` on the approved implementation branch with a unique nonce/timestamp commit. This is the only live trigger for the proof.

Expected: one `P0-B Strong-Zero Retry Live [OPS ONE-SHOT]` run starts.

- [ ] **Step 6: Observe the live run without automatic rerun**

Required step evidence:
- fresh census `strong_zero`;
- immutable snapshot/evidence pre-CAS gate PASS;
- one retry-authority CAS winner;
- one private draft creation;
- stable draft ID durable write;
- canonical reopen verification PASS;
- exact Notion queue readback PASS;
- durable final state `QUEUE_CONFIRMED`;
- model calls 0;
- public release false.

If the run fails after authorization or after any possible browser mutation, do not rerun; classify durable state first.

- [ ] **Step 7: Prove ordinary retry cannot create a duplicate**

Against the same prepared revision, invoke the ordinary delivery path once in bounded verification mode. Assert the existing operation is loaded with `creation_authorized=False`, browser create count remains 0 for this proof invocation, stable draft ID is unchanged, and durable state remains/reconciles to `QUEUE_CONFIRMED`.

- [ ] **Step 8: Record live evidence without sensitive identifiers**

Update the implementation branch documentation/PR summary with run ID, commit SHA, safe state transitions, PASS counts, zero-model/public-release claims, and duplicate-block result. Do not include raw sync ID, title, draft URL, draft ID, or GCS object name.

- [ ] **Step 9: Commit only evidence/docs changes, if any**

Do not merge. Wait for explicit `MERGE GO` before any main integration.

### Task 7: Remove Temporary Project-Wide Storage Admin and Re-Prove Hosted Ledger Access

**Files:**
- No production code change expected.
- Optional evidence-only documentation update after verification.

**Interfaces:**
- Consumes: successful Task 6 B01 and existing bucket-scoped object permissions.
- Produces: C-1 evidence that hosted WIF can continue production ledger reads/writes without temporary project-wide `roles/storage.admin`.

- [ ] **Step 1: Verify bucket hardening before privilege reduction**

Confirm Uniform Bucket-Level Access and Public Access Prevention are enforced and the service account retains the required bucket-scoped object permission.

- [ ] **Step 2: Remove temporary project-wide `Storage Admin`**

Because the current ChatGPT GitHub tooling does not administer Google Cloud project IAM, have the user remove only `roles/storage.admin` from `github-note-draft@aiif-note-draft.iam.gserviceaccount.com` in Google Cloud IAM. Do not remove unrelated legacy roles during this bounded proof.

- [ ] **Step 3: Re-run hosted ledger read/write CAS smoke**

Use the existing bounded private ledger smoke to create/update/delete only a temporary proof object with generation preconditions; then read the real delivery record read-only. No note/Notion mutation.

Expected: WIF auth PASS, bucket access PASS, generation-CAS PASS, production ledger read PASS, no project-wide Storage Admin required.

- [ ] **Step 4: Record C-1 evidence and stop before merge**

Record only safe IAM/bucket control outcomes. C-2 retention/backup/version-recovery remains separate. `main` remains untouched until explicit `MERGE GO`.
