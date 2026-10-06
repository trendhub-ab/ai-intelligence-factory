# P0-B Strong-Zero Retry Authority Design

Date: 2026-10-06
Status: Approved conversational design; written specification for review
Branch: `ops/p0b-hosted-b01-recovery-20261006`

## 1. Purpose

This specification defines how P0-B may safely re-authorize exactly one new private note draft creation attempt after a prior ambiguous creation has been proven absent by a fresh strong-zero census and durably reconciled to `MANUAL_RECONCILIATION_REQUIRED`.

The design must preserve the core P0-B invariant: ambiguous or existing delivery state never falls through to automatic duplicate creation.

## 2. Preconditions already proven in production

The current delivery has already completed phase-one reconciliation with the following evidence:

- the previous ambiguous B01 attempt stopped before draft mutation;
- a fresh authenticated private-draft census observed the private draft surface and returned `strong_zero`;
- target draft count was zero;
- suspicious blank and unreadable counts were zero;
- model calls were zero;
- note mutation count was zero;
- the current immutable `DeliverySnapshot` exactly matched the durable snapshot from the ambiguous attempt;
- the GCS ledger was CAS-transitioned from `CREATION_UNKNOWN` to `MANUAL_RECONCILIATION_REQUIRED`;
- durable readback confirmed no stable draft identity and `creation_authorized=false`.

These facts are audit evidence. They do not themselves restore creation authority.

## 3. Existing contracts that remain unchanged

The following P0-B rules remain binding:

- one logical delivery maps to one durable authority record;
- `logical_key`, `revision_key`, and `operation_key` remain derived from the existing identity and immutable snapshot contracts;
- normal `begin_or_load()` never restores creation authority for an existing operation;
- stable draft identity must be durably recorded before queue mutation;
- ambiguous creation never triggers an automatic second create;
- queue confirmation requires exact Notion readback;
- human-edit protection remains fail-closed;
- no model calls are required for this recovery path;
- no public release is permitted;
- no PC, self-hosted runner, OS username, UID/GID, systemd, or home-directory contract is introduced;
- production durable authority remains the private GCS object ledger using generation preconditions.

## 4. Rejected approaches

### 4.1 Generic state rollback

Do not add `MANUAL_RECONCILIATION_REQUIRED -> CREATE_INTENT_RECORDED` to `_ALLOWED_TRANSITIONS`.

Reason: a generic transition would let unrelated code paths re-enable creation and would weaken fail-closed semantics.

### 4.2 Delete or reset the existing ledger record

Do not delete the GCS object, clear event history, reset `state_version`, or recreate the record from scratch.

Reason: this destroys audit evidence and can reopen duplicate-creation races.

### 4.3 New attempt object plus mutable pointer

Do not split the retry into a second GCS attempt object plus a separate active-pointer object.

Reason: GCS provides generation-CAS per object, not an atomic multi-object transaction. The additional pointer would create a new consistency boundary without current need.

## 5. Selected architecture

Keep the same durable GCS object and the same logical/operation identity. Add a dedicated reconciliation-only ledger operation, conceptually:

`authorize_reconciled_retry(...)`

This operation is the only path allowed to restore creation authority after a strong-zero manual reconciliation.

Normal `begin_or_load()` remains unchanged and continues to return `creation_authorized=false` for the existing operation.

## 6. Authorization conditions

`authorize_reconciled_retry(...)` must fail closed unless all conditions below are true at the same read/CAS attempt:

1. the active durable record exists for the expected logical delivery;
2. state is exactly `MANUAL_RECONCILIATION_REQUIRED`;
3. the current immutable `DeliverySnapshot` exactly equals the durable snapshot;
4. `draft_id` is empty;
5. the durable reconciliation evidence category starts with `creation_absence_confirmed_strong_zero:`;
6. the evidence digest is non-empty and structurally valid;
7. the caller supplies the exact expected `state_version` observed immediately before authorization;
8. the underlying GCS write uses the exact observed generation as `ifGenerationMatch`;
9. no concurrent writer has modified the record;
10. the retry has not already been authorized.

Any mismatch results in zero creation authority and zero note mutation.

## 7. Dedicated state transition

On success, the dedicated operation performs exactly one durable transition:

`MANUAL_RECONCILIATION_REQUIRED -> CREATE_INTENT_RECORDED`

This transition is not exposed through generic `record_blocked()` or the ordinary `_ALLOWED_TRANSITIONS` table.

The successful CAS appends an audit event with category:

`strong_zero_retry_authorized:<evidence_digest>`

The prior event history is preserved unchanged, including:

- `CREATE_INTENT_RECORDED -> CREATION_UNKNOWN` from the failed attempt;
- `CREATION_UNKNOWN -> MANUAL_RECONCILIATION_REQUIRED` from strong-zero phase one.

The state version increments normally. It is never reset.

## 8. One-shot semantics

The CAS winner alone receives `creation_authorized=true` for that invocation.

The durable state change itself is the one-shot token. No reusable boolean flag or external marker grants authority.

If two workers attempt authorization concurrently:

- both may read the same eligible record;
- only one generation-matched write may succeed;
- the loser must receive `creation_authorized=false` or a concurrency failure and must not call the browser create path.

After authorization, a normal workflow retry still calls `begin_or_load()` and must not receive new authority merely because the record is `CREATE_INTENT_RECORDED`.

## 9. Crash and failure semantics

### 9.1 Failure before authorization CAS

No durable change and no creation authority.

### 9.2 Failure after authorization CAS but before note mutation

Do not automatically issue a second authorization. The record remains a consumed create intent. Recovery requires another explicit evidence-driven reconciliation cycle.

### 9.3 Failure during browser creation before durable stable ID

Preserve existing behavior:

`CREATE_INTENT_RECORDED -> CREATION_UNKNOWN`

No automatic second create.

### 9.4 Stable draft ID durably recorded

Once `DRAFT_CREATED` is recorded, never recreate. Continue only against that stable draft identity.

### 9.5 Canonical verification failure

Transition to `VERIFICATION_BLOCKED`; do not recreate.

### 9.6 Queue mutation ambiguity

Read back exact Notion queue binding first. Never recreate the draft because of queue ambiguity.

## 10. Runtime integration

The ordinary delivery path remains unchanged.

The retry path is a separate bounded operation with this sequence:

1. authenticate to GCP using existing GitHub Actions WIF;
2. select the exact eligible Ready candidate without model use;
3. reconstruct the current immutable snapshot;
4. verify durable state is `MANUAL_RECONCILIATION_REQUIRED`;
5. re-run a fresh authenticated strong-zero private-draft census;
6. require snapshot equality and durable strong-zero evidence;
7. call `authorize_reconciled_retry(...)` once;
8. only if that call returns `creation_authorized=true`, execute the existing private-draft browser creation path;
9. durably record stable draft identity;
10. reopen and perform canonical verification;
11. PATCH Notion queue binding;
12. exact-readback the queue binding;
13. transition to `QUEUE_CONFIRMED` only after exact confirmation.

If step 7 does not return authority, steps 8-13 must not run.

## 11. Implementation boundaries

Expected production changes:

- `note_delivery_ledger.py`
  - extend the `DeliveryLedger` protocol with a dedicated reconciled-retry authorization operation or an equivalent narrowly typed interface;
  - do not weaken generic transitions.

- `note_delivery_gcs.py`
  - implement dedicated generation-CAS authorization on the existing record object;
  - append the retry-authorization audit event atomically with the state update.

- `note_delivery_runtime.py`
  - preserve ordinary `begin_or_load()` semantics;
  - expose a bounded runtime helper for the authorized retry path without allowing ordinary retries to reuse the authority.

- strong-zero retry module/workflow
  - orchestrate fresh census, immutable snapshot check, dedicated authorization, and exactly one bounded B01 create path.

SQLite may receive an equivalent implementation only to preserve interface parity and offline tests. SQLite is not the production authority for hosted delivery.

## 12. Required tests

The implementation is not eligible for live proof until all of the following are covered:

1. non-strong-zero reconciliation cannot authorize retry;
2. snapshot drift cannot authorize retry;
3. generic `MANUAL_RECONCILIATION_REQUIRED` without strong-zero evidence cannot authorize retry;
4. existing stable draft ID blocks retry authorization;
5. stale `state_version` blocks retry authorization;
6. stale GCS generation blocks retry authorization;
7. two concurrent GCS callers yield at most one CAS winner;
8. only the CAS winner receives `creation_authorized=true`;
9. generic `_ALLOWED_TRANSITIONS` still rejects manual-reconciliation rollback;
10. ordinary `begin_or_load()` still does not re-authorize the existing operation;
11. authorization increments `state_version` and preserves prior event history;
12. authorization appends `strong_zero_retry_authorized:<digest>`;
13. failure after authorization but before browser mutation does not auto-authorize again;
14. browser ambiguity returns to `CREATION_UNKNOWN` and blocks automatic second create;
15. stable draft identity prevents recreation;
16. exact canonical verification remains required;
17. queue PATCH alone is insufficient; exact readback remains required;
18. model calls remain zero;
19. public release remains false;
20. hosted workflow contains no self-hosted/GCE/OS-user dependency.

Validation order:

- focused retry-authority tests;
- existing P0-B ledger/GCS/runtime tests;
- full pytest suite;
- Workflow Reference Guard;
- Repository Falsification Guard;
- Integration Stability Guard;
- `git diff --check`.

## 13. B01 live acceptance proof

After all offline validation is GREEN, run one bounded live proof only.

Required live sequence:

`fresh strong-zero census`
`-> immutable snapshot recheck`
`-> durable strong-zero evidence recheck`
`-> retry-authority generation-CAS`
`-> one private draft create`
`-> stable draft identity durable write`
`-> canonical reopen verification`
`-> exact Notion queue PATCH/readback`
`-> QUEUE_CONFIRMED`

Acceptance requires all of the following:

- exactly one retry authority winner;
- exactly one private draft for the logical delivery;
- stable draft identity durably bound;
- canonical verification PASS;
- exact queue readback PASS;
- durable state `QUEUE_CONFIRMED`;
- model calls zero;
- public release false;
- a subsequent ordinary preflight cannot obtain a second creation authority.

Any ambiguity stops the proof. There is no automatic repeated B01 dispatch.

## 14. Rollback policy

Rollback never means deleting or rewinding the ledger.

- before authorization CAS: stop with no durable mutation;
- after authorization CAS but before note mutation: stop and preserve consumed authority;
- ambiguous create: preserve `CREATION_UNKNOWN`;
- stable draft recorded: preserve and reconcile that exact draft;
- verification failure: preserve `VERIFICATION_BLOCKED`;
- queue ambiguity: read back exact binding before any further action.

Do not fall back to the old self-hosted VM path.

## 15. IAM hardening after successful B01

The current temporary project-wide `roles/storage.admin` grant is not the intended steady-state permission.

After B01 success:

- retain the private ledger bucket;
- verify Uniform Bucket-Level Access and Public Access Prevention remain enforced;
- retain only the bucket-scoped object permissions required by production ledger operations;
- remove the temporary project-wide Storage Admin role if no longer required;
- verify hosted production still reads/writes the ledger using WIF;
- record this as C-1 cloud access-boundary evidence.

C-2 retention/version-recovery verification remains a separate control and must not be conflated with retry authority.

## 16. Merge and publication gates

- No merge to `main` without explicit `MERGE GO` from the user.
- No automatic note publication.
- No model API calls are required by this design.
- No weakening of P0-A/C23, B2, B3, B4, Evidence, Fact, Human Appeal, or Publication gates.

## 17. Completion criteria

This design is complete only when:

- strong-zero reconciliation remains durable and auditable;
- generic retry paths cannot restore creation authority;
- a dedicated generation-CAS can authorize at most one retry;
- concurrent workers cannot both create;
- crash windows remain fail-closed;
- the bounded B01 live proof reaches `QUEUE_CONFIRMED` once;
- a subsequent ordinary retry proves duplicate creation remains blocked;
- IAM is reduced from temporary project-wide Storage Admin to the minimum steady-state permission set;
- `main` remains untouched until explicit `MERGE GO`.
