# P0-B Durable Delivery Ledger Design

Date: 2026-10-04
Repository: `trendhub-ab/ai-intelligence-factory`
Base main: `6f2c7b308ae2d49c4f34092dfbd682221d2bf040`
Status: design approved in chat; implementation not started

## 1. Purpose

Close the remaining P0-B delivery integrity gaps after P0-A/C23 and B-2 stable note draft identity were merged in PR #715.

This design covers:

- B-1: a private durable delivery ledger that is independent from the Notion queue;
- B-4: exact queue confirmation binding and readback;
- B-3: conservative human-edit protection for existing private note drafts;
- the immutable handoff required before any note-side mutation so a preflight-selected article cannot silently change between preflight and worker execution.

The primary business outcome is not maximum automation. It is to prevent duplicate note drafts, stale-revision delivery, accidental overwrite of human edits, and false queue success while keeping operating cost and system complexity low.

## 2. Non-goals

This change does not:

- publish note articles automatically;
- call Gemini or any model;
- weaken Evidence, Fact, Human Appeal, Publication, eyecatch, current-publication-policy, or canonical-body gates;
- make the Notion queue the authority for external draft existence;
- guarantee automatic recovery after an ambiguous note creation result;
- complete C-1/C-2 private storage IAM, backup, or final retention proof;
- add Firestore or Cloud SQL unless later evidence shows the existing persistent VM disk cannot meet the required durability and access contract;
- migrate or delete historical duplicate drafts automatically.

## 3. Existing contract to preserve

The merged system already has:

- a persistent Google Chrome note worker on a GCE VM;
- current-policy manuscript SHA validation;
- canonical note document verification across insert, save, reopen, and stable-ID reopen paths;
- stable private note draft identity extracted only from an exact note edit route;
- `note下書きID` plus `投稿準備中` written to the exact Notion queue row in one fail-closed PATCH;
- human-controlled public release only;
- zero-model note draft creation;
- no raw private draft URL in public result output.

The new ledger must wrap these contracts, not replace or relax them.

## 4. Chosen architecture

### 4.1 Store

Use a private SQLite ledger on the existing note GCE VM persistent boot disk.

Default path:

`~/.aiif-note/delivery-ledger-v1.sqlite3`

The exact path is configurable through a dedicated environment variable, but production must default to a private VM-local path outside the repository checkout and outside public/runtime artifact paths.

Reasons:

- lowest additional cost: no new managed database service;
- SQLite provides atomic transactions, uniqueness constraints, durable commits, and conditional state transitions;
- the note side effect already occurs on this VM, allowing write-ahead intent and immediate post-identity durable recording at the closest possible boundary;
- the ledger survives workflow process exit and VM stop/start;
- it is independent from Notion and GitHub Actions artifacts.

SQLite is an implementation choice, not the semantic authority. All application code must use a storage adapter so a future private managed store can replace it without changing delivery semantics.

### 4.2 Durability settings

The production SQLite connection must use conservative settings suitable for delivery authority:

- `PRAGMA journal_mode=WAL`;
- `PRAGMA synchronous=FULL`;
- foreign keys enabled;
- explicit transactions for every state transition;
- schema version stored in the database;
- file and parent directory permissions restricted to the note worker account where the platform permits it.

If the ledger cannot be opened, validated, or durably committed, new note creation is forbidden.

## 5. Identities and immutable snapshot

### 5.1 Logical delivery identity

A logical delivery is identified by:

- exact normalized `sync_id`;
- note account/target identity;
- destination surface = private note draft.

This identity owns at most one active draft binding at a time.

### 5.2 Revision identity

Before any note mutation, freeze an immutable delivery snapshot containing at minimum:

- exact `sync_id`;
- exact destination queue page ID;
- normalized title and title digest;
- byte-exact manuscript SHA-256;
- publication policy SHA-256;
- canonical document hash;
- canonical contract version;
- normalization policy version;
- presentation/transform version(s), including Run222-relevant transform identity;
- eyecatch image SHA-256 and asset identity;
- note target/account identity;
- Ready/current-publication provenance needed to prove eligibility.

The snapshot is serialized in one versioned canonical representation. The revision key is derived from that representation.

### 5.3 Operation idempotency key

The operation key is derived from:

- logical delivery identity;
- revision identity;
- operation-key schema version.

Workflow run ID, retry count, VM boot ID, or timestamp must not be part of the operation key. Retrying the same revision must produce the same operation key.

A new revision must not bypass an unresolved active logical delivery. If any active or ambiguous record exists for the same logical delivery, automatic new draft creation is blocked until reconciliation resolves it.

## 6. Ledger model

The storage adapter exposes semantic records; SQL details remain private to the adapter.

### 6.1 Delivery record

Each delivery record stores at minimum:

- record ID: random opaque internal identifier;
- schema version;
- logical delivery key;
- revision key;
- operation key;
- immutable snapshot payload or immutable snapshot digest plus required reconstruction fields;
- monotonic state;
- state version;
- attempt count;
- worker ownership metadata used only for coordination;
- created/updated timestamps;
- stable external draft ID when known;
- note edit-route host/account binding needed to validate ownership, without publishing the private URL;
- last verified canonical document hash;
- verification receipt metadata;
- exact destination queue page ID;
- queue confirmation receipt/readback metadata;
- conflict or ambiguity category when blocked.

Secrets, cookies, session state, manuscript body, arbitrary exception text, and raw DOM are not stored in the ledger.

### 6.2 Audit events

State changes append a private audit event with:

- opaque record ID;
- prior/new state;
- safe internal category;
- timestamp;
- originating run correlation;
- state version.

The event log is not a public Actions artifact and is not written to the public runtime-state branch.

## 7. State machine

Allowed primary states:

1. `PREPARED`
2. `CREATE_INTENT_RECORDED`
3. `DRAFT_CREATED`
4. `DRAFT_VERIFIED`
5. `QUEUE_CONFIRMATION_PENDING`
6. `QUEUE_CONFIRMED`
7. `CREATION_UNKNOWN`
8. `VERIFICATION_BLOCKED`
9. `CONFLICT`
10. `MANUAL_RECONCILIATION_REQUIRED`

Transitions are monotonic except for reconciliation transitions from pending/unknown/blocked states into a later proven state. Code must not reset a delivery to `PREPARED` in order to obtain another creation attempt.

### 7.1 Creation rule

A note creation side effect is legal only after `CREATE_INTENT_RECORDED` has been durably committed for the operation key and the logical-delivery active binding.

If intent commit fails, note creation count must be zero.

### 7.2 External identity rule

As soon as note exposes the stable exact private edit route, extract the opaque draft ID and durably record `DRAFT_CREATED` before queue mutation and before treating canonical verification as success.

If that durable record fails:

- do not update the queue;
- do not start another draft creation;
- retain/unresolved intent state and require reconciliation.

### 7.3 Verification rule

`DRAFT_VERIFIED` requires all of the existing production checks on the same stable draft identity:

- title persistence;
- canonical body equality;
- permitted note DOM normalization only;
- current revision identity;
- private editor state;
- required eyecatch persistence.

Failure preserves the known draft existence and transitions to `VERIFICATION_BLOCKED`; it never deletes and recreates automatically.

## 8. Preflight-to-worker immutable handoff

The current hosted preflight selects a `sync_id`; the worker later re-fetches mutable source state. That is insufficient for B16.

The new flow must:

1. hosted preflight identifies the exact eligible queue/source target using existing zero-VM rules;
2. worker re-fetches the source and computes the immutable snapshot immediately before acquiring ledger intent;
3. after intent is committed and immediately before the first note mutation, revalidate the source/queue against the snapshot-relevant identity and hashes;
4. if manuscript, policy, title, asset, queue identity, or eligibility changed, stop before note mutation;
5. the worker never silently substitutes a different candidate.

The hosted preflight result remains a scheduling/cost optimization. The VM-side immutable snapshot is the authoritative delivery revision.

## 9. Retry and reconciliation

Every write-enabled retry begins with the ledger, not with queue candidate selection alone.

Behavior by state:

- `QUEUE_CONFIRMED`: no note creation; return a safe reconciled-existing result;
- `QUEUE_CONFIRMATION_PENDING`: re-open/revalidate the same stable draft and reconcile queue only;
- `DRAFT_VERIFIED`: queue reconciliation only;
- `DRAFT_CREATED`: open the same stable draft and resume verification;
- `CREATE_INTENT_RECORDED`: investigate the existing creation intent; never fall back directly to new creation;
- `CREATION_UNKNOWN`: reconcile only; automatic new creation forbidden;
- `VERIFICATION_BLOCKED`: no queue confirmation and no recreation;
- `CONFLICT` / `MANUAL_RECONCILIATION_REQUIRED`: all automatic mutation blocked;
- ledger unavailable: creation zero.

A lease timeout alone is not proof that an old worker cannot still mutate note. Because note does not consume an internal fencing token, a replacement worker must not create a new draft while the prior side-effect status is ambiguous.

## 10. Queue confirmation binding (B-4)

Do not add a new Notion delivery-ID or revision column in the first implementation.

The private ledger is the authority and records:

- operation/revision key;
- exact queue page ID;
- exact `sync_id`;
- stable note draft ID.

The Notion queue projection continues to store:

- exact row identity;
- `同期ID`;
- `note下書きID`;
- `投稿状態=投稿準備中`.

Queue confirmation is complete only when:

1. the draft is already `DRAFT_VERIFIED` in the ledger;
2. the exact queue row is patched using the existing stable draft identity contract;
3. the exact queue row is read back;
4. readback shows the expected `sync_id`, stable draft ID, Ready quality state, and `投稿準備中` state;
5. only then the ledger records `QUEUE_CONFIRMED` with a queue confirmation receipt.

A queue PATCH timeout or 5xx never implies "not applied". Readback decides whether to retry the PATCH or remain pending.

## 11. Human edit protection (B-3)

Default policy: do not automatically overwrite an existing private draft.

For a future explicit in-place resync/update operation, mutation is permitted only when all are true:

- stable external draft identity matches the ledger active binding;
- draft is still private and belongs to the expected note target/account;
- current note canonical document hash exactly equals the ledger's last verified canonical hash;
- no creation/reconciliation ambiguity exists;
- the source revision is a newer explicitly eligible revision;
- the operation is an explicitly authorized update path, not normal draft creation retry.

If the current note hash differs from the last verified hash, classify as `HUMAN_EDIT_DETECTED` and transition to a blocked/manual state. Do not overwrite, create another draft, or advance the queue.

Also block automatic update/recreation when the bound draft is published, deleted, inaccessible, owned by another account, or otherwise ambiguous.

## 12. Crash-window policy

The system cannot make note's external draft creation and the SQLite commit one atomic transaction.

The unresolved dangerous window is:

`note accepted creation -> process crashed before stable draft ID was durably recorded`

Therefore:

- after an ambiguous creation result, automatic second creation is forbidden;
- if stable ID was already durably recorded, retry must reuse exactly that draft;
- if stable ID was not durably recorded and no reliable recovery evidence exists, transition to `CREATION_UNKNOWN` / manual reconciliation;
- availability is sacrificed before duplicate creation risk.

The guaranteed target is at-least-once execution with idempotent effect where the external identity is known, not "always finish automatically".

## 13. Privacy and public output

The ledger is private operational authority and must never be uploaded wholesale to GitHub Actions artifacts or written to the public runtime-state branch.

Public/Actions-visible output may contain only the existing safe operational projection, for example:

- component;
- safe status enum;
- opaque correlation ID not derived from `sync_id` or manuscript hash;
- aggregate counts;
- zero-model indicator.

Do not publish:

- `sync_id`;
- draft ID;
- draft URL;
- manuscript/revision hash;
- queue page ID;
- raw exception text;
- raw ledger rows;
- private filesystem paths.

C-1/C-2 remain open until actual VM/disk IAM, operator access, backup and retention behavior are independently evidenced.

## 14. Migration and existing drafts

No historical row is automatically trusted merely because it is `投稿準備中` or contains a draft ID.

For existing queue rows/drafts created before this ledger:

- read-only discovery may identify candidates;
- automatic migration requires exact stable draft identity plus current canonical verification and exact queue binding;
- ambiguous, missing, published, deleted, human-edited, or account-mismatched cases become manual reconciliation targets;
- migration must not create a new draft;
- duplicate drafts are not automatically deleted.

The first production enablement may be limited to new deliveries if existing-row migration evidence is insufficient.

## 15. Test design

Implementation uses TDD. Helper-only tests are insufficient; production entrypoints and installer order must be covered.

Required core cases:

- B01 normal create -> verify -> queue confirm: total successful drafts = 1;
- B02 queue timeout after creation: retry reuses draft, readback resolves application, total drafts = 1;
- B03 queue 5xx: verified draft remains, queue pending, retry creates zero drafts;
- B04 process crash at each boundary: before note accept, after accept/before ID record, after ID record/before verify, after verify/before queue, after queue/before ledger confirmation;
- B05 result/report write failure after queue success: state rebuilt from ledger/readback, total drafts = 1;
- B06 same operation-key retry: no second creation;
- B07 worker/process restart and temp loss: recover from durable ledger;
- B08 concurrent same-`sync_id` runs: only one creation authority;
- B09 same revision from a different workflow run: same operation key and same draft binding;
- B10 new legitimate manuscript revision: no automatic new draft; authorized update only if human-edit guard passes;
- B11 intent durable commit failure: creation zero;
- B12 stable external ID durable-write failure: queue update zero, new creation zero;
- B13 stale/expired coordination ownership while prior worker may live: replacement creation zero;
- B14 same title/body draft on another account: reuse blocked;
- B15 published/deleted/human-edited bound draft: overwrite/recreation blocked;
- B16 source/policy/asset change after preparation: block before note mutation;
- B17 policy/revision key changes while prior active intent unresolved: new creation blocked;
- B18 ledger unavailable while queue appears eligible: creation zero.

Critical acceptance criterion: after B02-B07 retries, the number of successfully created drafts for the logical delivery remains exactly one. In the unrecorded B04 ambiguity window, inability to auto-complete is acceptable; creating a second draft is not.

Additional tests:

- SQLite schema migration/version rejection;
- unique logical active binding;
- unique operation key;
- invalid/backward state transition rejection;
- WAL/FULL configuration assertion in production adapter;
- readback mismatch never records `QUEUE_CONFIRMED`;
- public-output sentinel test proving ledger/private identity never reaches stdout/stderr/summary/artifact;
- production installer/static guard proving legacy direct creation cannot bypass ledger intent.

## 16. Likely implementation impact

New module:

- `note_delivery_ledger.py`: semantic state model, snapshot/key generation, storage adapter interface, SQLite adapter, transitions, reconcile decisions, queue confirmation receipts.

Likely changed production files:

- `run194_note_persistent_cloud.py`: install ledger delivery wrapper after current/canonical contracts are installed;
- `note_publication_reconcile.py`: preserve B-2 identity helper but allow queue binding to be driven only after ledger verification;
- `run199_note_vm_preflight.py` and/or note draft worker handoff: preserve exact target and add immutable-worker validation contract;
- `run190_note_persistent_cloud.py`: expose a narrow hook/event when a stable draft route is first observed so `DRAFT_CREATED` can be persisted before later verification;
- `.github/workflows/note-create-draft.yml`: pass ledger path/config, run new zero-model ledger tests, and preserve safe public summaries;
- existing in-place resync code paths: install human-edit guard before any replacement mutation.

Likely new/updated tests:

- `tests/test_note_delivery_ledger.py`;
- integration tests around Run194/Run190/Run199;
- B01-B18 crash/retry/concurrency tests using a filesystem-backed temporary SQLite database, not an in-memory database;
- workflow/static tests ensuring no public ledger upload and no direct bypass.

Exact file list may narrow during implementation, but no unrelated refactor is authorized.

## 17. Rollout

Implementation remains disabled for production creation until all offline tests and repository guards pass.

Rollout sequence:

1. implement snapshot/key semantics and SQLite adapter behind tests;
2. integrate write-ahead intent and early stable-ID recording;
3. integrate canonical verification -> queue PATCH -> readback -> confirmation;
4. add retry/reconcile and human-edit protection;
5. run focused and full regression suites plus repository/workflow guards;
6. conduct one bounded private-draft live proof with zero model calls and no public release;
7. independently inspect actual VM ledger file permissions/disk access/backup/retention before claiming C-1/C-2;
8. only then decide production enablement and migration scope.

No merge to `main` occurs without explicit user `MERGE GO`.

## 18. Rollback

If the ledger implementation misbehaves:

- stop new note creation;
- retain the ledger and all unresolved records;
- do not revert to the legacy queue-only creation path;
- do not delete draft bindings to force retries;
- fix/reconcile from the durable state, then resume only after verification.

Application rollback must not enable a worker version that is unaware of ledger authority while active ledger records exist.

## 19. Completion criteria

P0-B implementation can be called technically complete only when:

- B01-B18 pass through production-connected code paths or faithful offline integration boundaries;
- B02-B07 retries demonstrate total draft count = 1;
- concurrent same-target execution cannot create two drafts;
- VM/process restart does not lose active delivery state;
- unknown creation never auto-recreates;
- exact queue PATCH readback is required for `QUEUE_CONFIRMED`;
- human edit detection blocks overwrite and duplicate creation;
- stable draft identity and canonical verification remain intact;
- no model calls and no public release are introduced;
- no private ledger/identity data appears in public output;
- bounded live private-draft proof succeeds.

C-1/C-2 remain separate closure criteria requiring real infrastructure evidence for access, backup, and retention.