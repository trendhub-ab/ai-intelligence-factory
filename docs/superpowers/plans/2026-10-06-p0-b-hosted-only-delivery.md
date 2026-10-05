# P0-B Hosted-Only Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the persistent self-hosted/GCE note runner and VM-local SQLite production ledger with a GitHub-hosted note draft workflow backed by a private GCS durable ledger, while preserving all P0-B duplicate-prevention, fail-closed, stable-identity, canonical verification, queue readback, and human-edit protections.

**Architecture:** Keep the existing semantic delivery state machine and runtime orchestration, but introduce a storage-neutral ledger protocol plus a GCS adapter that uses object-generation preconditions as the serialization/CAS boundary. Convert `.github/workflows/note-create-draft.yml` to run the entire zero-model browser path on `ubuntu-latest` with GitHub OIDC/WIF before GCS ledger access; remove GCE start/stop, self-hosted labels, VM-local ledger configuration, OS-account assumptions, and persistent-home requirements from the production path.

**Tech Stack:** Python 3.11, pytest/unittest, GitHub Actions, Playwright/Chrome or Chromium, `google-cloud-storage`, GitHub OIDC + Google Workload Identity Federation, Google Cloud Storage generation preconditions, Notion API.

**Spec:** `docs/superpowers/specs/2026-10-06-p0-b-hosted-only-delivery-design.md`

## Global Constraints

- Production note draft creation must run on GitHub-hosted runners only.
- No personal PC, self-hosted runner, systemd runner service, runner OS username, UID/GID, or persistent home directory may be required.
- `NOTE_STORAGE_STATE_B64` remains an ephemeral runtime input; decoded browser state must be removed during cleanup.
- Production durable authority is a private GCS object ledger, not Notion and not GitHub artifacts.
- First GCS record creation must use generation-match `0`; every later mutation must use the last observed generation.
- No unconditional GCS overwrite path is allowed.
- `CREATION_UNKNOWN` never grants automatic second-create authority.
- Stable note draft identity must be durably recorded before queue mutation.
- Exact Notion readback is required before `QUEUE_CONFIRMED`.
- Human-edit detection must still block overwrite/recreation.
- No Gemini/OpenAI/model calls may be introduced into note draft creation.
- No automatic public release may be introduced.
- No private bucket name, object key, raw `sync_id`, draft identity/URL, queue page ID, manuscript/revision hash, auth state, or raw ledger object may appear in public Actions output.
- No merge to `main` without explicit user `MERGE GO`.

## Review Focus

1. **Two hosted runs race on the same logical delivery:** exactly one generation-0 create may win; the loser re-reads and never creates a draft.
2. **GCS write succeeds but the Actions process dies before local state updates:** retry must reconstruct authority from GCS and never rely on in-memory ownership.
3. **Storage-state/session expiry on a fresh hosted runner:** fail closed before creation when detectable and never attempt credential-login automation.
4. **GCS transient error or stale generation during a state transition:** treat as zero new creation authority, re-read/reconcile, never unconditional retry-write.
5. **Queue PATCH timeout after a verified draft:** exact readback decides state; draft recreation remains forbidden.

---

## File Structure

- `note_delivery_ledger.py` — keep state model, snapshot/key logic, transition rules, shared record serialization, and storage-neutral `DeliveryLedger` protocol; retain `SQLiteDeliveryLedger` for offline/reference tests only.
- `note_delivery_gcs.py` — new production GCS ledger adapter implementing the same semantic interface using generation preconditions.
- `note_delivery_runtime.py` — depend on the storage-neutral ledger interface; factory chooses GCS in production from environment; remove VM-path default from production behavior.
- `note_delivery_ledger_preflight.sh` — switch read-only production preflight from local SQLite path assumptions to the configured cloud-ledger factory.
- `.github/workflows/note-create-draft.yml` — hosted-only job graph, OIDC/WIF before ledger access, hosted browser install, no GCE/self-hosted/OS-user assumptions.
- `tests/test_note_delivery_ledger.py` — preserve semantic/SQLite reference cases; move production-adapter assertions out of SQLite-only assumptions.
- `tests/test_note_delivery_gcs.py` — new fake-client unit tests for generation/CAS, serialization, malformed records, and race semantics.
- `tests/test_note_delivery_runtime.py` — prove runtime is storage-neutral, GCS factory behavior, ephemeral auth cleanup, and retry semantics.
- `tests/test_p0b_production_installation.py` — hosted-only/static production guards.
- Existing Run190/194/199 and human-edit tests — rerun unchanged unless a narrow expectation explicitly names VM/self-hosted behavior.

---

### Task 1: Extract a storage-neutral durable-ledger contract

**Files:**
- Modify: `note_delivery_ledger.py`
- Modify: `note_delivery_runtime.py`
- Test: `tests/test_note_delivery_ledger.py`
- Test: `tests/test_note_delivery_runtime.py`

**Interfaces:**
- Produces protocol `DeliveryLedger` with:
  - `get_by_operation_key(op_key: str) -> DeliveryRecord | None`
  - `get_active_by_logical_key(logical_key: str) -> DeliveryRecord | None`
  - `begin_or_load(snapshot: DeliverySnapshot, *, run_correlation_id: str) -> IntentDecision`
  - `record_draft_created(operation_key: str, *, draft_id: str, note_host: str, expected_version: int) -> DeliveryRecord`
  - `record_verified(operation_key: str, *, canonical_sha256: str, expected_version: int) -> DeliveryRecord`
  - `record_queue_pending(operation_key: str, *, category: str, expected_version: int) -> DeliveryRecord`
  - `record_queue_confirmed(operation_key: str, *, receipt_digest: str, expected_version: int) -> DeliveryRecord`
  - `record_blocked(operation_key: str, *, state: DeliveryState, category: str, expected_version: int) -> DeliveryRecord`
- Produces `delivery_record_to_dict(record: DeliveryRecord) -> dict[str, object]` and `delivery_record_from_dict(data: Mapping[str, object]) -> DeliveryRecord` with strict schema/state validation.
- `SQLiteDeliveryLedger` continues to satisfy `DeliveryLedger` but is no longer the production default.

- [ ] **Step 1: Write failing protocol/serialization tests**

Add tests asserting a `DeliveryRecord` round-trips through `delivery_record_to_dict`/`delivery_record_from_dict`, unsupported `schema_version` fails with `LedgerSchemaError`, invalid state fails closed, and `SQLiteDeliveryLedger` satisfies the protocol surface used by runtime.

- [ ] **Step 2: Run focused tests to prove RED**

Run: `python -m pytest tests/test_note_delivery_ledger.py tests/test_note_delivery_runtime.py -q`

Expected: FAIL because the protocol and shared serialization functions do not yet exist and runtime is typed to `SQLiteDeliveryLedger`.

- [ ] **Step 3: Implement the protocol and shared serialization**

Add `DeliveryLedger(Protocol)` and strict shared record serialization in `note_delivery_ledger.py`. Generalize `_reconcile_queue_projection`, `_resume_existing_delivery`, `require_inplace_update_allowed`, and `create_or_resume_delivery` in `note_delivery_runtime.py` from `SQLiteDeliveryLedger` to `DeliveryLedger` without changing state semantics.

- [ ] **Step 4: Run focused tests to GREEN**

Run: `python -m pytest tests/test_note_delivery_ledger.py tests/test_note_delivery_runtime.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add note_delivery_ledger.py note_delivery_runtime.py tests/test_note_delivery_ledger.py tests/test_note_delivery_runtime.py
git commit -m "refactor: make P0-B delivery ledger storage-neutral"
```

---

### Task 2: Implement the GCS production ledger with generation-CAS semantics

**Files:**
- Create: `note_delivery_gcs.py`
- Create: `tests/test_note_delivery_gcs.py`
- Modify: `note_delivery_ledger.py` only if a storage-neutral helper is required by the adapter

**Interfaces:**
- Consumes the `DeliveryLedger` protocol and shared record serialization from Task 1.
- Produces `GCSDeliveryLedger(bucket_name: str, *, prefix: str = "delivery/v1", client: object | None = None)` implementing `DeliveryLedger`.
- Produces deterministic object name `record_object_name(logical_key: str) -> str` where only the hashed logical key appears after the fixed private prefix.
- GCS adapter maps generation/precondition failure to `ConcurrentStateChange`; transport/unavailable errors to `LedgerUnavailableError`; malformed/schema-invalid JSON to `LedgerSchemaError`.

- [ ] **Step 1: Write failing GCS adapter tests with an in-memory fake blob/client**

Tests must cover: deterministic opaque key; no raw `sync_id` in object name; first `begin_or_load` writes with generation-match `0`; same operation retry grants no create; different revision under active logical key grants no create; stale-generation transition raises `ConcurrentStateChange`; concurrent generation-0 attempts produce one `creation_authorized=True`; malformed/unsupported record fails closed; no write helper allows an absent generation precondition.

- [ ] **Step 2: Run GCS tests to prove RED**

Run: `python -m pytest tests/test_note_delivery_gcs.py -q`

Expected: FAIL because `note_delivery_gcs.py` does not exist.

- [ ] **Step 3: Implement `GCSDeliveryLedger` minimally**

Use `google.cloud.storage.Client` only behind the constructor/import boundary so fake-client tests require no network. Each read returns both decoded `DeliveryRecord` and observed object generation internally. Each mutation writes the complete canonical record JSON with `if_generation_match=<observed_generation>`; first record uses `if_generation_match=0`. Never perform an unconditional upload.

- [ ] **Step 4: Pin Review Focus race/crash behavior**

Add tests simulating: winner write followed by loser stale write; successful durable write followed by local exception/retry; transient read/write exception. Assert no path returns fresh creation authority without a successful generation-guarded durable record.

- [ ] **Step 5: Run GCS + semantic ledger tests**

Run: `python -m pytest tests/test_note_delivery_gcs.py tests/test_note_delivery_ledger.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add note_delivery_gcs.py tests/test_note_delivery_gcs.py note_delivery_ledger.py
git commit -m "feat: add GCS durable delivery ledger"
```

---

### Task 3: Make hosted production runtime choose the cloud ledger and keep auth ephemeral

**Files:**
- Modify: `note_delivery_runtime.py`
- Modify: `note_delivery_ledger_preflight.sh`
- Modify: `run194_note_persistent_cloud.py` only where production naming/config assumes VM-local storage
- Test: `tests/test_note_delivery_runtime.py`
- Test: `tests/test_p0b_production_installation.py`

**Interfaces:**
- Produces environment contract:
  - `NOTE_DELIVERY_LEDGER_BACKEND=gcs` for production.
  - `NOTE_DELIVERY_LEDGER_BUCKET=<private bucket>` required when backend is `gcs`.
  - `NOTE_DELIVERY_LEDGER_PREFIX=delivery/v1` optional fixed-safe prefix.
- Produces `delivery_ledger_from_environment() -> DeliveryLedger` selecting `GCSDeliveryLedger` for `gcs`; SQLite remains explicit test/reference backend only and must not be implicit production fallback.

- [ ] **Step 1: Write failing factory/runtime tests**

Assert: `backend=gcs` with bucket returns `GCSDeliveryLedger`; missing bucket raises fail-closed `LedgerUnavailableError`; unknown backend fails; production-default path does not silently create `~/.aiif-note/...`; storage-state temp file is deleted on success and browser failure; auth/session failure does not grant new create authority.

- [ ] **Step 2: Run focused tests to RED**

Run: `python -m pytest tests/test_note_delivery_runtime.py tests/test_p0b_production_installation.py -q`

Expected: FAIL on current SQLite path default and VM-specific assumptions.

- [ ] **Step 3: Implement backend factory and remove implicit VM-local production fallback**

Update runtime and preflight wrapper so production selection is explicit and GCS-backed. Keep SQLite available only when explicitly configured by tests/reference tooling.

- [ ] **Step 4: Normalize residual VM wording only where it affects behavior/contracts**

Replace error/status text such as “VM preparation returned…” with compute-neutral wording. Do not rename unrelated historical Run files solely for aesthetics.

- [ ] **Step 5: Run runtime, human-edit, Run194 and install guards**

Run:
```bash
python -m pytest \
  tests/test_note_delivery_runtime.py \
  tests/test_note_delivery_human_edit_guard.py \
  tests/test_p0b_production_installation.py -q
python -m unittest tests.test_run194_note_current_contract -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add note_delivery_runtime.py note_delivery_ledger_preflight.sh run194_note_persistent_cloud.py tests/test_note_delivery_runtime.py tests/test_p0b_production_installation.py
git commit -m "feat: select cloud ledger for hosted note delivery"
```

---

### Task 4: Convert `note-create-draft.yml` to a single hosted-only production path

**Files:**
- Modify: `.github/workflows/note-create-draft.yml`
- Modify: `tests/test_p0b_production_installation.py`
- Modify: `tests/test_run199_note_vm_preflight.py` only for compute-neutral output naming/expectations required by the workflow

**Interfaces:**
- Hosted draft job runs on `ubuntu-latest`.
- Job permissions include `contents: read` and `id-token: write` only where WIF is required.
- GCP auth via `google-github-actions/auth@v3` occurs before any GCS ledger read/write.
- Install runtime dependencies on hosted runner: `requests`, `playwright`, `google-cloud-storage`, existing test dependencies, then install a supported Chromium/Chrome runtime through Playwright or an explicitly verified hosted image path.
- Set `NOTE_CHROME_HEADLESS=true` unless current browser contract proves headed mode is required; do not require `xvfb-run` or persistent Chrome.
- Set `NOTE_DELIVERY_LEDGER_BACKEND=gcs`, bucket from repository variable/secret, safe prefix, and existing `NOTE_STORAGE_STATE_B64`.
- Remove `start-cloud-vm`, `stop-cloud-vm`, `runs-on: [self-hosted,...]`, GCE instance variables/commands, VM wait logic, `NOTE_DELIVERY_LEDGER_PATH`, `xvfb-run`, and system-installed Chrome checks.

- [ ] **Step 1: Write failing hosted-only static workflow tests**

Assert production workflow contains no `self-hosted`, no `gcloud compute instances start|stop`, no `GCP_NOTE_VM_*`, no `NOTE_DELIVERY_LEDGER_PATH`, no `~/.aiif-note`, and no `xvfb-run`; it must contain `ubuntu-latest`, `id-token: write`, `google-github-actions/auth@v3`, `NOTE_DELIVERY_LEDGER_BACKEND: 'gcs'`, bucket configuration, hosted Playwright browser installation, and existing zero-model/no-public-release guards.

- [ ] **Step 2: Run production-installation test to RED**

Run: `python -m pytest tests/test_p0b_production_installation.py -q`

Expected: FAIL on current self-hosted/GCE workflow.

- [ ] **Step 3: Rewrite the job graph minimally**

Retain current preflight and exact-candidate pinning semantics, but remove VM scheduling. Prefer `preflight -> create-draft` with `create-draft` depending only on preflight. Authenticate to GCP before durable-ledger preflight. Run browser tests/setup only when ledger says delivery work is required.

- [ ] **Step 4: Pin session-expiry and queue-timeout behavior**

Ensure workflow surfaces only safe status enums and still leaves retry authority to the ledger/runtime. No workflow branch may call creation after `ledger_blocked_ambiguous`, auth failure, or queue ambiguity.

- [ ] **Step 5: Run workflow/install and existing note contract tests**

Run:
```bash
python -m pytest tests/test_p0b_production_installation.py tests/test_note_delivery_runtime.py -q
python -m unittest \
  tests.test_note_draft_automation \
  tests.test_run185_note_ready_legacy_skip \
  tests.test_run186_note_header_image_resilience \
  tests.test_run187_note_editor_readiness \
  tests.test_run188_note_header_upload_fallback \
  tests.test_run189_note_editor_route_gate \
  tests.test_run190_note_persistent_cloud \
  tests.test_run191_note_crop_dialog_resilience \
  tests.test_run193_note_official_header_upload \
  tests.test_run194_publication_contract \
  tests.test_run194_note_current_contract \
  tests.test_run199_note_vm_preflight -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/note-create-draft.yml tests/test_p0b_production_installation.py tests/test_run199_note_vm_preflight.py
git commit -m "feat: run note delivery on GitHub-hosted runners"
```

---

### Task 5: Full regression, falsification, prepare-only proof, and bounded B01 live proof

**Files:**
- Modify tests/guards only if they reveal a real regression; do not weaken assertions to obtain green.
- Update PR #716 description or open a replacement hosted-only PR after branch verification; do not merge.

**Interfaces:**
- Completion signal for offline implementation: all focused tests + full pytest + repository/workflow guards GREEN.
- Production proof signal: one private draft delivery reaches durable `QUEUE_CONFIRMED`, exact Notion readback confirms the same stable draft binding, model calls = 0, public release = 0.

- [ ] **Step 1: Run B01-B18 focused semantic suite**

Run:
```bash
python -m pytest \
  tests/test_note_delivery_ledger.py \
  tests/test_note_delivery_gcs.py \
  tests/test_note_delivery_runtime.py \
  tests/test_note_delivery_human_edit_guard.py \
  tests/test_run295_note_eyecatch_persistence.py \
  tests/test_p0b_eyecatch_callback_forwarding.py \
  tests/test_p0b_production_installation.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full repository test suite and repository guards**

Run the repository's current canonical full pytest command plus Workflow Reference Guard, Repository Falsification Guard, Integration Stability Guard, and `git diff --check` against the latest main merge base.

Expected: all GREEN; existing known warnings may remain only if unchanged and documented.

- [ ] **Step 3: Inspect diff specifically for forbidden production dependencies**

Search changed production workflow/runtime files for: `self-hosted`, `aiif-note-cloud`, `systemctl`, runner service/user references, UID/GID ownership, `GCP_NOTE_VM_`, `gcloud compute instances`, VM-local ledger path, and personal-PC assumptions.

Expected: none in the production delivery path. Historical docs/tests may mention them only as legacy assertions/reference.

- [ ] **Step 4: Verify required cloud configuration read-only before live execution**

Confirm repository WIF variables are present for auth and the configured private GCS ledger bucket is reachable with the production principal. Verify access is limited to the intended production principal/operators before calling C-1 closed. Do not print bucket/object/private identity values into public logs.

- [ ] **Step 5: Trigger one `prepare_only=true` workflow dispatch**

Expected: hosted preflight succeeds, zero browser mutation, zero note draft creation, zero model calls, no GCE/self-hosted job is scheduled.

- [ ] **Step 6: Trigger exactly one bounded B01 private-draft live proof**

Use `confirm=CREATE_NOTE_DRAFT`, `prepare_only=false`, and at most one exact eligible target selected by the existing preflight contract. Expected terminal state: `queue_confirmed` / durable `QUEUE_CONFIRMED`, one successful private draft, exact queue readback, zero model calls, zero automatic public release.

If note creation becomes ambiguous, stop. Do not dispatch a second create. Inspect the GCS ledger and reconcile first.

- [ ] **Step 7: Verify durable retry behavior without creating a second draft**

Re-read the ledger/queue for the B01 operation and prove a same-operation retry would resume/reconcile the existing binding rather than receive new creation authority. Do not perform an unnecessary second live mutation merely to demonstrate this if read-only evidence plus existing B02-B07 tests suffice.

- [ ] **Step 8: Update PR evidence; do not merge**

Record hosted-only architecture, exact test/guard results, prepare-only result, B01 result, zero-model/public-release evidence, and any still-open C-1/C-2 items. Leave merge pending explicit `MERGE GO`.

- [ ] **Step 9: Commit any evidence-only documentation changes**

```bash
git add <only changed evidence/docs files>
git commit -m "docs: record hosted-only P0-B verification"
```
