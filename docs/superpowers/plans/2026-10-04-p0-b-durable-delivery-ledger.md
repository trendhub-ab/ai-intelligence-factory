# P0-B Durable Delivery Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed private durable delivery ledger so note draft creation, verification, queue confirmation, retries, and explicit in-place updates cannot create duplicate drafts, accept stale revisions, overwrite human edits, or report false queue success.

**Architecture:** Keep the existing note GCE VM and PR #715 canonical/stable-ID contracts. Add a file-backed SQLite authority on the VM persistent disk, a small runtime orchestration layer that performs immutable snapshot validation and ledger-first reconciliation, and exact Notion queue readback before confirmation. Hosted preflight remains a cost/scheduling gate; VM-side snapshot + ledger state is the delivery authority.

**Tech Stack:** Python 3.11, stdlib `sqlite3`, `dataclasses`, `enum`, `hashlib`, existing Playwright note path, existing Notion adapter, existing `note_document_contract` canonical parser/renderer, pytest/unittest tests, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-04-p0-b-durable-delivery-ledger-design.md`

## Global Constraints

- Production base is main `6f2c7b308ae2d49c4f34092dfbd682221d2bf040`; re-check main before execution and account for any later P0-relevant diff.
- Use private SQLite at `~/.aiif-note/delivery-ledger-v1.sqlite3` by default; allow one dedicated environment-variable override for tests/operations.
- Production SQLite must use `journal_mode=WAL`, `synchronous=FULL`, foreign keys enabled, explicit transactions, and a schema version.
- A note creation side effect is legal only after durable `CREATE_INTENT_RECORDED` for the exact operation key and active logical binding.
- Stable note draft identity must be durably recorded as `DRAFT_CREATED` immediately after the exact private edit route becomes observable and before canonical reopen verification or queue mutation.
- The Notion queue remains a projection. It is never the authority for whether a draft exists.
- Do not add a new Notion delivery-ID/revision column in the first implementation; bind through private ledger + exact queue row + `同期ID` + `note下書きID` + `投稿状態` readback.
- No automatic second draft after ambiguous creation; availability yields to duplicate prevention.
- Default B-3 policy is no automatic overwrite. Explicit in-place update requires the current canonical hash to equal the ledger's last verified hash.
- No automatic trust/migration of pre-ledger `投稿準備中` rows or historical draft IDs.
- Zero Gemini/model calls; no automatic note publication; human-controlled public release remains unchanged.
- Never publish `sync_id`, draft ID/URL, queue page ID, manuscript/revision hash, ledger rows, raw exception text, or private filesystem paths.
- C-1/C-2 stay open until real VM/disk access, backup, and retention are independently evidenced.
- No merge to `main` without explicit user `MERGE GO`.
- Live note/Notion/GCP mutation is not part of this plan execution; bounded live proof requires separate approval after offline verification.

## Review Focus

- **Corrupt/wrong-version ledger file:** initialization must fail closed and creation count must remain zero; Task 2 adds file-backed corruption/schema-version tests.
- **Different revision while one logical delivery is active/ambiguous:** the new revision must not obtain creation authority; Task 2 adds active-binding conflict tests and Task 6 adds B17 reconciliation coverage.
- **Queue row changes between PATCH and readback:** `QUEUE_CONFIRMED` must never be recorded when `sync_id`, draft ID, Ready state, or `投稿準備中` differs; Task 5 pins every field.
- **Stale worker or expired coordination metadata:** expiry alone must never grant a replacement worker creation authority; Task 2 adds B13 concurrency coverage.
- **Bound draft changed by a human or external action:** explicit update must block before replacement mutation and must not create another draft; Task 7 covers hash drift, published/deleted/foreign/inaccessible cases.

---

## File Structure

### New files

- `note_delivery_ledger.py` — pure delivery identity/snapshot model, deterministic keys, SQLite schema/transactions/state transitions, active logical binding, private event receipts. No Playwright or Notion calls.
- `note_delivery_runtime.py` — production orchestration: build/revalidate the VM-side snapshot, choose create vs reconcile from ledger state, receive early stable-ID callbacks, drive canonical verification state, bind/read back queue state, and expose explicit in-place-update guard.
- `tests/test_note_delivery_ledger.py` — file-backed SQLite unit/adversarial tests for keys, durability, transitions, concurrency, corruption, and B08/B11/B13/B17/B18.
- `tests/test_note_delivery_runtime.py` — offline integration tests for B01-B07, B09-B12, B14-B18 using fake note/queue surfaces and a real temporary SQLite file.

### Existing files expected to change

- `note_draft_automation.py` — add an optional stable-draft-route callback at the exact first stable URL boundary; preserve existing callers by defaulting to `None`.
- `run190_note_persistent_cloud.py` — thread that optional callback through the persistent-Chrome override without changing browser/session behavior.
- `note_publication_reconcile.py` — retain B-2 route parsing and atomic queue patch, add exact queue binding readback/verification primitives used by P0-B runtime.
- `run194_note_persistent_cloud.py` — install P0-B runtime after existing current-contract, Run222, eyecatch, and B-2 installers so no earlier gate is weakened.
- `run199_note_vm_preflight.py` — for an explicit already-delivered target, allow a reconciliation-only VM start instead of permanently suppressing ledger repair; automatic empty-queue behavior remains zero-VM.
- `.github/workflows/note-create-draft.yml` — configure the private ledger path, run new offline ledger/runtime tests, preserve safe summaries, and never upload the ledger.
- `run298_genrec_inplace_refresh.py` — require ledger binding and human-edit hash guard before any explicit in-place mutation; stop relying on title/history as authority.
- `tests/test_note_draft_automation.py` — stable-route callback timing/backward-compatibility tests.
- `tests/test_run190_note_persistent_cloud.py` — callback propagation and no browser-lifecycle regression.
- `tests/test_note_publication_reconcile.py` — exact queue patch/readback binding tests.
- `tests/test_run194_note_current_contract.py` — snapshot-relevant current-policy/asset drift integration coverage if needed by runtime boundary.
- `tests/test_run199_note_vm_preflight.py` — explicit reconcile-only VM decision tests.
- `tests/test_run297_298_genrec_refresh.py` — B-3 no-binding/human-edit/published/foreign blocking tests.
- existing workflow/static security tests — extend only where needed to prove no ledger artifact/path/identity is public and no direct legacy creation bypass remains.

---

### Task 1: Deterministic delivery snapshot and identity keys

**Files:**
- Create: `note_delivery_ledger.py`
- Create: `tests/test_note_delivery_ledger.py`
- Reference: `note_document_contract.py`
- Reference: `run222_note_presentation_integrity.py`

**Interfaces:**
- Consumes: `note_document_contract.Document`, `normalize_document`, `render_safe_html`, `CONTRACT_VERSION`, `NORMALIZATION_POLICY_VERSION`.
- Produces: `DeliverySnapshot`, `DeliveryState`, `canonical_document_sha256(document)`, `build_delivery_snapshot(...)`, `logical_delivery_key(snapshot)`, `revision_key(snapshot)`, `operation_key(snapshot)`.

- [ ] **Step 1: Write RED tests for deterministic canonical identity**

Add tests named:

```python
def test_same_revision_has_same_operation_key_across_runs_and_retries(): ...
def test_manuscript_policy_asset_title_or_canonical_change_changes_revision_key(): ...
def test_run_id_retry_count_and_timestamp_are_not_operation_key_material(): ...
def test_canonical_document_hash_is_stable_for_proven_nfc_equivalence(): ...
def test_sync_id_and_target_change_logical_delivery_key(): ...
```

Assertions must use the spec fields: exact normalized `sync_id`, queue page ID, title digest, source manuscript SHA-256, publication policy SHA-256, canonical document hash, canonical contract version, normalization policy version, transform versions, eyecatch SHA/asset identity, note target, and Ready provenance.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m pytest tests/test_note_delivery_ledger.py -q`

Expected: FAIL because `note_delivery_ledger` and its snapshot/key interfaces do not exist.

- [ ] **Step 3: Implement the snapshot/key interfaces**

In `note_delivery_ledger.py`, define:

```python
class DeliveryState(str, Enum): ...

@dataclass(frozen=True)
class DeliverySnapshot:
    schema_version: str
    sync_id: str
    queue_page_id: str
    title_digest: str
    manuscript_sha256: str
    publication_policy_sha256: str
    canonical_document_sha256: str
    canonical_contract_version: str
    normalization_policy_version: str
    transform_versions: tuple[tuple[str, str], ...]
    eyecatch_sha256: str
    eyecatch_asset_id: str
    note_target: str
    ready_provenance: str


def canonical_document_sha256(document: Document) -> str: ...
def build_delivery_snapshot(...) -> DeliverySnapshot: ...
def logical_delivery_key(snapshot: DeliverySnapshot) -> str: ...
def revision_key(snapshot: DeliverySnapshot) -> str: ...
def operation_key(snapshot: DeliverySnapshot) -> str: ...
```

Use one versioned canonical JSON serialization with sorted keys and fixed separators. Hash the normalized canonical document through deterministic `render_safe_html(normalize_document(document))`; do not hash `repr()` or process-dependent structures.

- [ ] **Step 4: Run Task 1 tests GREEN**

Run: `python -m pytest tests/test_note_delivery_ledger.py -q`

Expected: all Task 1 tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add note_delivery_ledger.py tests/test_note_delivery_ledger.py
git commit -m "feat: define durable note delivery identity"
```

---

### Task 2: File-backed SQLite authority, state machine, and logical exclusion

**Files:**
- Modify: `note_delivery_ledger.py`
- Modify: `tests/test_note_delivery_ledger.py`

**Interfaces:**
- Consumes: Task 1 `DeliverySnapshot`, keys, `DeliveryState`.
- Produces: `DeliveryRecord`, `IntentDecision`, `SQLiteDeliveryLedger(path)`, `initialize()`, `get_by_operation_key()`, `get_active_by_logical_key()`, `begin_or_load()`, `record_draft_created()`, `record_verified()`, `record_queue_pending()`, `record_queue_confirmed()`, `record_blocked()`.

- [ ] **Step 1: Write RED tests for persistence and production PRAGMAs**

Add:

```python
def test_file_backed_ledger_survives_close_and_reopen(): ...
def test_production_adapter_uses_wal_full_and_foreign_keys(): ...
def test_unknown_schema_version_fails_closed(): ...
def test_corrupt_database_fails_closed_and_grants_no_creation_authority(): ...
```

Use `TemporaryDirectory()` + a real `.sqlite3` file, never `:memory:` for durability claims.

- [ ] **Step 2: Write RED tests for transitions and exclusion**

Add:

```python
def test_b11_intent_commit_failure_grants_zero_creation_authority(): ...
def test_b08_concurrent_same_logical_delivery_has_one_creation_authority(): ...
def test_same_operation_key_retry_loads_existing_record(): ...
def test_different_revision_cannot_bypass_active_logical_binding(): ...
def test_invalid_backward_state_transition_is_rejected(): ...
def test_b13_expired_owner_does_not_authorize_replacement_creation(): ...
def test_ledger_unavailable_b18_is_fail_closed(): ...
```

- [ ] **Step 3: Run Task 2 tests and verify RED**

Run: `python -m pytest tests/test_note_delivery_ledger.py -q`

Expected: new persistence/transition/concurrency tests FAIL while Task 1 identity tests remain PASS.

- [ ] **Step 4: Implement SQLite schema and transaction boundaries**

Implement `SQLiteDeliveryLedger` with three focused tables:

- `deliveries`: one row per operation/revision, unique `operation_key`;
- `logical_bindings`: one row per logical delivery, points at the active delivery/draft binding;
- `delivery_events`: append-only private state transition receipts.

Use `BEGIN IMMEDIATE` for creation-authority acquisition and expected `state_version` compare/update for later transitions. `initialize()` must validate schema version rather than silently replacing an unknown schema.

- [ ] **Step 5: Implement monotonic transition methods**

Signatures:

```python
def begin_or_load(self, snapshot: DeliverySnapshot, *, run_correlation_id: str) -> IntentDecision: ...
def record_draft_created(self, operation_key: str, *, draft_id: str, note_host: str, expected_version: int) -> DeliveryRecord: ...
def record_verified(self, operation_key: str, *, canonical_sha256: str, expected_version: int) -> DeliveryRecord: ...
def record_queue_pending(self, operation_key: str, *, category: str, expected_version: int) -> DeliveryRecord: ...
def record_queue_confirmed(self, operation_key: str, *, receipt_digest: str, expected_version: int) -> DeliveryRecord: ...
def record_blocked(self, operation_key: str, *, state: DeliveryState, category: str, expected_version: int) -> DeliveryRecord: ...
```

Do not store manuscript body, raw DOM, cookies, session data, private URL, secrets, or arbitrary exception text.

- [ ] **Step 6: Run Task 2 GREEN and prove restart durability**

Run: `python -m pytest tests/test_note_delivery_ledger.py -q`

Expected: all identity, persistence, transition, corruption, and concurrency tests PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add note_delivery_ledger.py tests/test_note_delivery_ledger.py
git commit -m "feat: add private sqlite delivery ledger"
```

---

### Task 3: VM-side immutable snapshot and pre-mutation revalidation

**Files:**
- Create: `note_delivery_runtime.py`
- Create: `tests/test_note_delivery_runtime.py`
- Modify: `run199_note_vm_preflight.py`
- Modify: `tests/test_run199_note_vm_preflight.py`
- Reference: `run194_note_current_contract.py`
- Reference: `run222_note_presentation_integrity.py`

**Interfaces:**
- Consumes: Task 1/2 ledger APIs; existing prepared article fields `sync_id`, `destination_page_id`, `title`, `manuscript`, `eyecatch_url`, `publication_contract`, `publication_policy_sha256`, `manuscript_sha256`.
- Produces: `PreparedDelivery`, `prepare_delivery(base, requested_sync_id)`, `revalidate_before_mutation(base, prepared)`, and explicit preflight status `reconcile_existing` for an exact already-delivered target.

- [ ] **Step 1: Write RED tests for B16 immutable handoff**

In `tests/test_note_delivery_runtime.py`, add:

```python
def test_snapshot_is_built_after_run222_presentation_transform(): ...
def test_b16_manuscript_change_blocks_before_note_mutation(): ...
def test_b16_policy_change_blocks_before_note_mutation(): ...
def test_b16_title_change_blocks_before_note_mutation(): ...
def test_b16_eyecatch_identity_change_blocks_before_note_mutation(): ...
def test_queue_page_or_ready_eligibility_change_blocks_before_note_mutation(): ...
```

The fake browser creation counter must remain zero in every drift case.

- [ ] **Step 2: Add RED preflight reconciliation tests**

In `tests/test_run199_note_vm_preflight.py`, pin:

```python
def test_explicit_already_delivered_target_starts_vm_for_reconciliation_only(): ...
def test_automatic_empty_safe_queue_still_does_not_start_vm(): ...
```

Expected explicit result: `status == "reconcile_existing"`, `should_start_vm is True`, selected sync ID is the exact requested ID, and no model/browser call occurs in preflight.

- [ ] **Step 3: Run Task 3 tests and verify RED**

Run: `python -m pytest tests/test_note_delivery_runtime.py tests/test_run199_note_vm_preflight.py -q`

Expected: immutable-runtime interfaces/status do not yet exist.

- [ ] **Step 4: Implement `PreparedDelivery` and snapshot construction**

In `note_delivery_runtime.py` define:

```python
@dataclass(frozen=True)
class PreparedDelivery:
    article: Mapping[str, Any]
    snapshot: DeliverySnapshot
    eyecatch_path: Path


def prepare_delivery(base: Any, requested_sync_id: str) -> PreparedDelivery: ...
def revalidate_before_mutation(base: Any, prepared: PreparedDelivery) -> None: ...
```

Build the canonical document from the already-transformed note-body manuscript using the PR #715 parser/normalizer. Use the exact downloaded eyecatch bytes for `eyecatch_sha256`. The second source/queue read immediately before note mutation must match snapshot-relevant fields; it must not silently choose another candidate.

- [ ] **Step 5: Change explicit already-delivered preflight to reconciliation-only VM start**

In `run199_note_vm_preflight.preflight()`, change only the explicit `already_delivered` branch to return `reconcile_existing` + `should_start_vm=True`. Keep automatic no-eligible behavior zero-VM and keep all preflight paths zero-browser/zero-model.

- [ ] **Step 6: Run Task 3 GREEN**

Run: `python -m pytest tests/test_note_delivery_runtime.py tests/test_run199_note_vm_preflight.py tests/test_run194_note_current_contract.py -q`

Expected: PASS; existing current-publication-contract tests remain GREEN.

- [ ] **Step 7: Commit Task 3**

```bash
git add note_delivery_runtime.py tests/test_note_delivery_runtime.py run199_note_vm_preflight.py tests/test_run199_note_vm_preflight.py
git commit -m "feat: freeze note delivery revision before mutation"
```

---

### Task 4: Write-ahead intent and immediate stable-draft-ID durable recording

**Files:**
- Modify: `note_draft_automation.py`
- Modify: `run190_note_persistent_cloud.py`
- Modify: `note_delivery_runtime.py`
- Modify: `tests/test_note_draft_automation.py`
- Modify: `tests/test_run190_note_persistent_cloud.py`
- Modify: `tests/test_note_delivery_runtime.py`

**Interfaces:**
- Consumes: Task 2 `begin_or_load()` and `record_draft_created()`; existing exact stable edit route parser from `note_publication_reconcile.draft_identity_from_url()`.
- Produces: optional callback `on_stable_draft_url: Callable[[str], None] | None` on the browser save path; creation runtime that cannot call note before intent durability.

- [ ] **Step 1: Write RED callback-order tests**

Add tests proving:

```python
def test_stable_route_callback_runs_after_url_observation_before_reopen_verification(): ...
def test_existing_callers_without_callback_keep_current_behavior(): ...
def test_persistent_cloud_override_forwards_stable_route_callback(): ...
```

Use call-order sentinels: `stable_url_observed -> callback -> page.goto(reopen) -> canonical verification`.

- [ ] **Step 2: Write RED B11/B12/B04 boundary tests**

In `tests/test_note_delivery_runtime.py`, add:

```python
def test_b11_note_creation_is_zero_when_intent_commit_fails(): ...
def test_b12_draft_id_durable_write_failure_prevents_queue_update_and_second_create(): ...
def test_b04_after_id_record_before_verify_retry_reuses_same_draft(): ...
def test_b04_after_accept_before_id_record_becomes_creation_unknown_not_second_create(): ...
```

- [ ] **Step 3: Run Task 4 tests and verify RED**

Run: `python -m pytest tests/test_note_draft_automation.py tests/test_run190_note_persistent_cloud.py tests/test_note_delivery_runtime.py -q`

Expected: callback/order and write-ahead tests FAIL.

- [ ] **Step 4: Add the optional stable-route callback at the earliest proven boundary**

Update signatures without breaking old callers:

```python
def _save_draft_and_verify(..., *, on_stable_draft_url: Callable[[str], None] | None = None) -> str: ...
def _create_browser_draft(..., *, on_stable_draft_url: Callable[[str], None] | None = None) -> str: ...
```

Invoke the callback immediately after `_wait_for_draft_url()` returns and before reopening that URL. Thread the keyword through `run190_note_persistent_cloud._create_browser_draft()`.

- [ ] **Step 5: Gate runtime creation on durable intent and record opaque identity in callback**

Add to `note_delivery_runtime.py`:

```python
def create_or_resume_delivery(base: Any, ledger: SQLiteDeliveryLedger, prepared: PreparedDelivery, *, run_correlation_id: str) -> DeliveryRecord: ...
```

When the ledger grants creation authority, revalidate Task 3 snapshot, then call browser creation with a callback that parses the exact stable route and calls `record_draft_created()`. If callback persistence fails, no queue mutation is allowed and the logical binding remains unresolved/unknown.

- [ ] **Step 6: Run Task 4 GREEN**

Run: `python -m pytest tests/test_note_draft_automation.py tests/test_run190_note_persistent_cloud.py tests/test_note_delivery_runtime.py -q`

Expected: PASS, including callback timing and zero-second-create assertions.

- [ ] **Step 7: Commit Task 4**

```bash
git add note_draft_automation.py run190_note_persistent_cloud.py note_delivery_runtime.py tests/test_note_draft_automation.py tests/test_run190_note_persistent_cloud.py tests/test_note_delivery_runtime.py
git commit -m "feat: persist note draft identity before verification"
```

---

### Task 5: Canonical verification state and exact queue confirmation readback

**Files:**
- Modify: `note_publication_reconcile.py`
- Modify: `note_delivery_runtime.py`
- Modify: `tests/test_note_publication_reconcile.py`
- Modify: `tests/test_note_delivery_runtime.py`

**Interfaces:**
- Consumes: existing B-2 exact route parser and queue patch; Task 2 `record_verified()`, `record_queue_pending()`, `record_queue_confirmed()`.
- Produces: `QueueDraftBinding`, `read_queue_draft_binding(page_id)`, `patch_and_readback_draft_binding(...)`, runtime transition `DRAFT_CREATED -> DRAFT_VERIFIED -> QUEUE_CONFIRMATION_PENDING/QUEUE_CONFIRMED`.

- [ ] **Step 1: Write RED queue-binding tests**

In `tests/test_note_publication_reconcile.py`, add:

```python
def test_queue_binding_readback_requires_exact_sync_id_draft_id_ready_and_preparing(): ...
def test_patch_timeout_but_applied_is_resolved_by_readback_without_second_patch(): ...
def test_patch_5xx_and_unapplied_remains_pending(): ...
def test_readback_sync_id_mismatch_is_conflict_not_confirmed(): ...
def test_readback_draft_id_mismatch_is_conflict_not_confirmed(): ...
def test_readback_quality_or_posting_state_mismatch_is_not_confirmed(): ...
```

- [ ] **Step 2: Add RED runtime B01-B03/B05 tests**

```python
def test_b01_verified_draft_exact_readback_reaches_queue_confirmed(): ...
def test_b02_queue_timeout_retry_creates_no_second_draft(): ...
def test_b03_queue_5xx_keeps_verified_draft_and_pending_state(): ...
def test_b05_queue_applied_then_result_failure_is_reconstructible_from_ledger_and_readback(): ...
```

- [ ] **Step 3: Run Task 5 tests and verify RED**

Run: `python -m pytest tests/test_note_publication_reconcile.py tests/test_note_delivery_runtime.py -q`

Expected: exact binding/readback helpers and confirmation transitions are missing.

- [ ] **Step 4: Implement exact queue readback primitives**

Define:

```python
@dataclass(frozen=True)
class QueueDraftBinding:
    page_id: str
    sync_id: str
    quality: str
    posting: str
    draft_id: str


def read_queue_draft_binding(destination_page_id: str, *, error_type: type[Exception] = RuntimeError) -> QueueDraftBinding: ...
def patch_and_readback_draft_binding(destination_page_id: str, *, expected_sync_id: str, draft_id: str, error_type: type[Exception] = RuntimeError) -> QueueDraftBinding: ...
```

Preserve `mark_draft_created()` as a compatibility wrapper if existing callers/tests need it. A timeout/5xx must trigger readback before deciding whether a second PATCH is needed; never infer non-application from transport failure alone.

- [ ] **Step 5: Record `DRAFT_VERIFIED` only after existing canonical same-draft proof, then queue confirmation**

In runtime, canonical verification success records the verified canonical hash first. Only then call queue patch/readback. Mismatch/transport ambiguity records pending/conflict without recreating a draft.

- [ ] **Step 6: Run Task 5 GREEN**

Run: `python -m pytest tests/test_note_publication_reconcile.py tests/test_note_delivery_runtime.py tests/test_run417_note_body_verification.py tests/test_run292_note_rendered_body_audit.py -q`

Expected: PASS; PR #715 canonical verifier regressions remain GREEN.

- [ ] **Step 7: Commit Task 5**

```bash
git add note_publication_reconcile.py note_delivery_runtime.py tests/test_note_publication_reconcile.py tests/test_note_delivery_runtime.py
git commit -m "feat: confirm note queue binding by exact readback"
```

---

### Task 6: Ledger-first retry/reconcile and crash-window behavior

**Files:**
- Modify: `note_delivery_runtime.py`
- Modify: `note_delivery_ledger.py`
- Modify: `tests/test_note_delivery_runtime.py`
- Modify: `tests/test_note_delivery_ledger.py`

**Interfaces:**
- Consumes: Task 2 state lookup/transitions; Tasks 4-5 creation and queue binding.
- Produces: `reconcile_exact_delivery(base, ledger, sync_id, note_target)`, safe result states `queue_confirmed`, `reconciled_existing`, `queue_confirmation_pending`, `creation_unknown`, `verification_blocked`, `manual_reconciliation_required`.

- [ ] **Step 1: Write the full B02-B09/B17/B18 retry matrix as RED tests**

Pin total fake note creation count after first attempt + retry:

```python
def test_b02_retry_after_queue_timeout_total_drafts_is_one(): ...
def test_b03_retry_after_queue_5xx_total_drafts_is_one(): ...
def test_b04_retry_at_each_crash_boundary_never_creates_second_draft(): ...
def test_b05_reporting_failure_reconstructs_result_without_create(): ...
def test_b06_same_operation_key_retry_total_drafts_is_one(): ...
def test_b07_process_restart_with_reopened_sqlite_total_drafts_is_one(): ...
def test_b08_second_worker_same_logical_delivery_cannot_create(): ...
def test_b09_same_revision_different_run_reconciles_existing_record(): ...
def test_b17_new_revision_with_unresolved_old_intent_cannot_create(): ...
def test_b18_unavailable_ledger_overrides_eligible_queue_and_creates_zero(): ...
```

The B04 “accepted before ID durable record” variant may end in `creation_unknown`; it must not auto-complete by creating another draft.

- [ ] **Step 2: Run retry matrix and verify RED**

Run: `python -m pytest tests/test_note_delivery_runtime.py tests/test_note_delivery_ledger.py -q`

Expected: retry/reconcile decisions are incomplete; no test may pass by resetting state to `PREPARED`.

- [ ] **Step 3: Implement ledger-first reconcile decision table**

Define:

```python
def reconcile_exact_delivery(base: Any, ledger: SQLiteDeliveryLedger, *, sync_id: str, note_target: str) -> dict[str, Any]: ...
```

Decision order must be ledger state first for an exact target. `QUEUE_CONFIRMED`, `DRAFT_VERIFIED`, `QUEUE_CONFIRMATION_PENDING`, `DRAFT_CREATED`, `CREATE_INTENT_RECORDED`, and `CREATION_UNKNOWN` must never fall through to normal new-draft creation.

- [ ] **Step 4: Implement process-restart/result reconstruction from durable state**

Close and reopen the file-backed ledger in B07/B05 tests. Reconstruct safe result fields from ledger + exact queue readback; do not require temp result files to prove delivery.

- [ ] **Step 5: Run Task 6 GREEN and assert the key acceptance criterion**

Run: `python -m pytest tests/test_note_delivery_runtime.py tests/test_note_delivery_ledger.py -q`

Expected: PASS and every B02-B07 test explicitly asserts total successful created draft count is exactly `1` except the unrecorded ambiguous B04 case, which asserts no second create.

- [ ] **Step 6: Commit Task 6**

```bash
git add note_delivery_runtime.py note_delivery_ledger.py tests/test_note_delivery_runtime.py tests/test_note_delivery_ledger.py
git commit -m "feat: reconcile note delivery from durable state"
```

---

### Task 7: B-3 human-edit protection for explicit in-place updates

**Files:**
- Modify: `note_delivery_runtime.py`
- Modify: `run298_genrec_inplace_refresh.py`
- Modify: `tests/test_note_delivery_runtime.py`
- Modify: `tests/test_run297_298_genrec_refresh.py`

**Interfaces:**
- Consumes: active logical binding + ledger `last_verified_canonical_hash`; PR #715 DOM/canonical audit of the bound exact draft.
- Produces: `require_inplace_update_allowed(...)` returning the bound record only when update is safe; otherwise a fixed blocked category such as `human_edit_detected`, `bound_draft_published`, `bound_draft_missing`, `bound_draft_foreign`, or `preledger_binding_requires_manual_reconciliation`.

- [ ] **Step 1: Write RED generic B10/B14/B15 tests**

Add:

```python
def test_b10_new_revision_never_creates_new_draft_automatically(): ...
def test_exact_bound_private_draft_with_unchanged_hash_may_enter_explicit_update_path(): ...
def test_human_edit_hash_drift_blocks_before_paste(): ...
def test_b14_same_title_body_foreign_account_draft_is_rejected(): ...
def test_b15_published_deleted_or_inaccessible_bound_draft_is_blocked(): ...
def test_missing_preledger_binding_requires_manual_reconciliation(): ...
```

- [ ] **Step 2: Add RED Run298 production-path tests**

In `tests/test_run297_298_genrec_refresh.py`, prove `refresh_existing_private_draft()` cannot reach `_paste_manuscript()` unless the exact persisted draft ID matches the ledger active binding and the pre-update canonical hash equals the ledger last verified hash. Remove title/history uniqueness as an authority; it may remain discovery-only for legacy diagnostics, not authorization.

- [ ] **Step 3: Run Task 7 tests and verify RED**

Run: `python -m pytest tests/test_note_delivery_runtime.py tests/test_run297_298_genrec_refresh.py -q`

Expected: current Run298 lacks ledger/human-edit authorization.

- [ ] **Step 4: Implement the generic in-place update guard**

Define:

```python
def require_inplace_update_allowed(
    ledger: SQLiteDeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
    draft_id: str,
    current_canonical_sha256: str,
    private_state: bool,
    account_matches: bool,
) -> DeliveryRecord: ...
```

Any mismatch blocks without overwriting, without creating another draft, and without queue advancement.

- [ ] **Step 5: Install B-3 guard into Run298 before any body/image mutation**

Use exact queue `note下書きID` + ledger binding as identity. If this historical target lacks a ledger record, fail closed with manual reconciliation; do not migrate it merely from Chrome history/title/body similarity.

- [ ] **Step 6: Run Task 7 GREEN**

Run: `python -m pytest tests/test_note_delivery_runtime.py tests/test_run297_298_genrec_refresh.py -q`

Expected: PASS; zero new-draft surfaces remain in Run298.

- [ ] **Step 7: Commit Task 7**

```bash
git add note_delivery_runtime.py run298_genrec_inplace_refresh.py tests/test_note_delivery_runtime.py tests/test_run297_298_genrec_refresh.py
git commit -m "feat: block note resync over human edits"
```

---

### Task 8: Production Run194 installation, workflow configuration, and public-boundary guards

**Files:**
- Modify: `run194_note_persistent_cloud.py`
- Modify: `.github/workflows/note-create-draft.yml`
- Modify: `note_delivery_runtime.py`
- Modify: relevant Run194/workflow/static tests discovered in current main
- Test: `tests/test_note_delivery_runtime.py`
- Test: `tests/test_run194_note_current_contract.py`
- Test: `tests/test_p0c_public_information_containment.py`

**Interfaces:**
- Consumes: Tasks 1-7 complete runtime.
- Produces: installed zero-model ledger-controlled `base.run`; private ledger path configured on the self-hosted VM; safe Actions result projection; static guarantee that legacy queue-only creation cannot bypass ledger intent.

- [ ] **Step 1: Write RED installer-order and bypass tests**

Pin the production installer order:

1. persistent Chrome install;
2. current publication contract;
3. Run222 presentation transform;
4. eyecatch persistence guard;
5. B-2 stable identity primitives;
6. P0-B durable delivery runtime last.

Tests must fail if Run194 write-enabled creation can call `_create_browser_draft()` without a ledger `CREATE_INTENT_RECORDED` decision.

- [ ] **Step 2: Write RED public-output/workflow tests**

Use synthetic sentinels for `sync_id`, draft ID/URL, queue page ID, revision hash, private ledger path, and raw ledger row. Assert none can reach stdout, stderr, GitHub step summary, Actions artifacts, or public runtime-state. Assert `.github/workflows/note-create-draft.yml` contains no upload step/glob that can select the ledger file.

- [ ] **Step 3: Run Task 8 tests and verify RED**

Run: `python -m pytest tests/test_note_delivery_runtime.py tests/test_run194_note_current_contract.py tests/test_p0c_public_information_containment.py -q`

Expected: installer/workflow ledger contract is not yet wired.

- [ ] **Step 4: Install runtime after all existing Run194 gates**

Add `note_delivery_runtime.install(cloud.base)` only after B-2 is installed. The runtime may reuse B-2 parsing/patch primitives but must own write-enabled creation/reconcile ordering.

- [ ] **Step 5: Configure private production ledger path and offline tests in workflow**

Set a dedicated environment variable such as `NOTE_DELIVERY_LEDGER_PATH` to the private VM path. Add `tests.test_note_delivery_ledger` and `tests.test_note_delivery_runtime` to the zero-model test step. Do not echo the path to public summary and do not upload the database/WAL/SHM files.

- [ ] **Step 6: Preserve pre-ledger safety policy**

When an exact `投稿準備中`/draft-ID target has no authoritative ledger binding, return a safe manual-reconciliation status. Do not create a new draft, automatically backfill the ledger, or delete a historical draft.

- [ ] **Step 7: Run Task 8 GREEN**

Run:

```bash
python -m pytest \
  tests/test_note_delivery_ledger.py \
  tests/test_note_delivery_runtime.py \
  tests/test_note_draft_automation.py \
  tests/test_run190_note_persistent_cloud.py \
  tests/test_note_publication_reconcile.py \
  tests/test_run194_note_current_contract.py \
  tests/test_run199_note_vm_preflight.py \
  tests/test_run297_298_genrec_refresh.py \
  tests/test_run417_note_body_verification.py \
  tests/test_run292_note_rendered_body_audit.py \
  tests/test_p0c_public_information_containment.py -q
```

Expected: PASS, zero external-service calls in tests.

- [ ] **Step 8: Commit Task 8**

```bash
git add run194_note_persistent_cloud.py .github/workflows/note-create-draft.yml note_delivery_runtime.py tests
git commit -m "feat: enforce durable ledger on note delivery"
```

---

### Task 9: Whole-repository falsification and PR-ready evidence

**Files:**
- Modify only if a failing guard reveals a real regression; otherwise no production-file changes.
- No live note/Notion/GCP mutation in this task.

**Interfaces:**
- Consumes: completed P0-B implementation.
- Produces: fresh offline evidence that B01-B18, PR #715 lossless/B2 contracts, P0-C public boundary, and repository-wide guards all remain GREEN.

- [ ] **Step 1: Run focused P0-B suite**

Run:

```bash
python -m pytest \
  tests/test_note_delivery_ledger.py \
  tests/test_note_delivery_runtime.py \
  tests/test_note_draft_automation.py \
  tests/test_run190_note_persistent_cloud.py \
  tests/test_note_publication_reconcile.py \
  tests/test_run194_note_current_contract.py \
  tests/test_run199_note_vm_preflight.py \
  tests/test_run297_298_genrec_refresh.py -q
```

Expected: PASS. Confirm B02-B07 each assert draft total `1` after retry (except the explicitly unrecorded ambiguous B04 variant, which asserts no second creation).

- [ ] **Step 2: Run P0-A/P0-C regression set**

Run:

```bash
python -m pytest \
  tests/test_run417_note_body_verification.py \
  tests/test_run292_note_rendered_body_audit.py \
  tests/test_p0c_public_information_containment.py -q
```

Expected: PASS; no canonical comparator relaxation and no reopened public raw-output route.

- [ ] **Step 3: Run the full current test suite**

Run: `python -m pytest tests -q`

Expected: 0 failures. Record pass count and warnings exactly; do not reuse PR #715's historical `3398 passed` as current evidence.

- [ ] **Step 4: Run repository/static guards**

Run:

```bash
python workflow_reference_guard.py
python repository_falsification_guard.py
python integration_stability_guard.py
git diff --check
```

Expected: all guards PASS and `git diff --check` exits 0.

- [ ] **Step 5: Falsify no-model/no-public-release and no-ledger-publication properties**

Search the final diff and write-enabled note entrypoints. Confirm:

- no Gemini/model client added;
- no note public-release action added;
- no ledger/identity URL/hash/path in public output;
- no public artifact/runtime-state persistence of SQLite/WAL/SHM;
- no direct legacy creation path reachable without ledger intent.

- [ ] **Step 6: Re-check branch base before opening PR**

Compare the implementation branch to current `main`. If main advanced from `6f2c7b308ae2d49c4f34092dfbd682221d2bf040`, inspect every intervening P0-relevant change before rebasing/merging; do not assume no impact.

- [ ] **Step 7: Open PR without merging**

PR description must include:

- exact base/head SHA;
- B01-B18 result summary;
- full current pytest result;
- guard results;
- explicit `zero model calls`, `no public release`, and `no live external mutation during offline verification`;
- statement that C-1/C-2 remain open;
- statement that bounded private live proof still requires separate approval;
- `Do not merge yet` until explicit user `MERGE GO`.

- [ ] **Step 8: Stop for bounded-live approval**

Do not run a production note draft, mutate the production queue, provision/change GCP storage/IAM, or claim C-1/C-2 complete. Present the PR/offline evidence and request separate approval for one bounded private-draft proof and infrastructure read-only evidence collection.
