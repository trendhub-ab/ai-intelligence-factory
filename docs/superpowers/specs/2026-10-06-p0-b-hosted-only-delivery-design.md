# P0-B Hosted-Only Durable Delivery Design

Date: 2026-10-06
Repository: `trendhub-ab/ai-intelligence-factory`
Base main: `6f2c7b308ae2d49c4f34092dfbd682221d2bf040`
Working branch: `design/p0-b-durable-delivery-ledger`
Status: superseding infrastructure design; implementation not started

## 1. Decision

Remove the persistent self-hosted note runner and its OS-account dependency from the P0-B delivery path.

The production delivery path becomes GitHub-hosted only:

`GitHub-hosted preflight -> durable cloud ledger -> Playwright/Chrome -> note private draft -> canonical reopen verification -> exact Notion queue readback -> QUEUE_CONFIRMED`

No PC, self-hosted runner, GCE runner registration, systemd runner service, runner username, UID/GID, or home-directory ownership is part of the delivery contract.

This design supersedes the VM/SQLite infrastructure choice in `2026-10-04-p0-b-durable-delivery-ledger-design.md`. The semantic P0-B contracts in that document remain binding unless explicitly changed here.

## 2. Goals

- eliminate OS-user identity as an operational dependency;
- preserve duplicate-prevention and fail-closed delivery semantics;
- preserve zero-model private-draft creation;
- preserve stable note draft identity and lossless canonical verification;
- preserve exact queue confirmation binding/readback;
- keep recurring infrastructure cost near zero;
- keep private delivery authority independent from Notion and GitHub public artifacts.

## 3. Non-goals

This change does not:

- automatically publish note articles;
- weaken Evidence, Fact, Human Appeal, Publication, eyecatch, or canonical-body gates;
- make the Notion queue authoritative for draft existence;
- authorize second-create after an ambiguous external creation;
- migrate historical ambiguous ledger rows by inference;
- require a continuously running VM or container service;
- require a personal PC.

## 4. Chosen architecture

### 4.1 Compute

Use GitHub-hosted `ubuntu-latest` runners for the complete note draft workflow.

The workflow installs/uses:

- Python 3.11;
- Playwright;
- a supported Chrome/Chromium runtime;
- current note automation and canonical verification code.

Authentication state continues to enter through GitHub Secrets, including the existing `NOTE_STORAGE_STATE_B64` contract. Authentication state is materialized only in the ephemeral job workspace and must be deleted during cleanup.

### 4.2 Durable authority

Replace VM-local SQLite with a private Google Cloud Storage object ledger.

Use one private bucket dedicated to delivery authority. The bucket name is supplied through repository configuration and must not be embedded in public summaries.

The bucket is not a generic artifact store. It stores only the minimum private delivery records and safe audit events required by P0-B.

Reasons:

- survives GitHub-hosted runner destruction;
- no persistent OS account or filesystem owner is required;
- no continuously running service;
- very low operating cost at current AIIF scale;
- GCS object generations provide atomic compare-and-swap semantics suitable for optimistic concurrency;
- Workload Identity Federation already exists in the repository's GCP control plane.

Firestore/Cloud SQL are explicitly deferred because they add operational surface without a demonstrated need at the current workload.

## 5. Ledger storage model

### 5.1 Record key

Each logical delivery maps to a deterministic, non-reversible object key derived from:

- normalized `sync_id`;
- note target identity;
- destination surface;
- key schema version.

The raw `sync_id`, title, manuscript hash, queue page ID, and draft ID must not appear in object names.

### 5.2 Record contents

Each record stores the same semantic authority required by the original P0-B design:

- schema version;
- logical delivery key;
- revision key;
- operation key;
- immutable delivery snapshot or required reconstruction fields;
- monotonic state and state version;
- attempt metadata;
- stable external draft ID when known;
- canonical verification receipt;
- exact queue binding and queue confirmation receipt;
- ambiguity/conflict category;
- created/updated timestamps.

Do not store cookies, session storage, manuscript body, raw DOM, arbitrary exception text, or public URLs.

### 5.3 Atomicity and concurrency

All state transitions use GCS generation preconditions:

- first record creation: create only with generation-match `0`;
- later transition: write only if the observed generation still matches;
- generation mismatch means another worker won the race; the losing worker must re-read and reconcile, never continue from stale state;
- no unconditional overwrite is permitted.

This is the replacement for SQLite transactions/uniqueness constraints.

For a single logical delivery, the GCS record is the serialization point.

## 6. State machine

Preserve the existing states:

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

Transitions remain monotonic. There is no state reset to obtain new create authority.

## 7. Creation authority

A note creation side effect is legal only after the worker has successfully committed `CREATE_INTENT_RECORDED` with a generation-guarded durable write.

If the durable write fails or conflicts:

- note creation count = 0;
- re-read ledger;
- reconcile from the new durable state.

If the external note creation result is ambiguous, transition to `CREATION_UNKNOWN` when safely possible and forbid automatic second creation.

## 8. Stable external identity

As soon as note exposes the exact private edit route, extract the stable draft identity and durably record `DRAFT_CREATED` through generation-guarded update before:

- queue mutation;
- treating canonical verification as terminal success;
- allowing any retry path to consider a new creation.

Failure to durably record the external ID means queue update = 0 and second-create authority = 0.

## 9. Hosted-only note automation

### 9.1 Browser execution

The hosted runner performs the current zero-model note automation using Playwright and a supported Chrome/Chromium runtime.

The workflow must not depend on:

- an existing user profile directory;
- a systemd service;
- OS-level persistent cookies;
- a fixed UID/GID;
- a persistent home directory.

The browser context is recreated from `NOTE_STORAGE_STATE_B64` for each job.

### 9.2 Authentication failure

If storage state is expired or note rejects the session:

- stop before creation when detectable;
- otherwise fail closed at the first protected operation;
- do not attempt credential re-login automation;
- do not create a second draft;
- return a safe authentication-required status.

## 10. Immutable snapshot and source revalidation

Preserve the existing immutable snapshot semantics.

Before acquiring create authority, compute the authoritative revision snapshot on the hosted runner. Immediately before first note mutation, revalidate all revision-relevant fields.

Any manuscript, policy, title, asset, queue-identity, or eligibility change blocks note mutation.

The workflow never silently substitutes another candidate.

## 11. Queue confirmation

Preserve B-4 exactly:

1. ledger state is `DRAFT_VERIFIED`;
2. patch the exact Notion queue row with the existing stable draft identity contract;
3. read back the exact queue row;
4. verify exact `sync_id`, stable draft ID, expected Ready quality state, and `投稿準備中`;
5. only then transition the cloud ledger to `QUEUE_CONFIRMED`.

PATCH timeout/5xx is not treated as unapplied. Readback determines the next action.

## 12. Human-edit protection

Preserve the existing P0-B human-edit guard.

Any future update/resync of an already-bound draft is allowed only when the current note canonical hash equals the last verified ledger hash and all ownership/private-state checks pass.

Mismatch is `HUMAN_EDIT_DETECTED` and blocks overwrite/recreation.

## 13. Privacy and IAM

The GCS bucket must be private and accessible only through the production GitHub Actions Workload Identity principal/service account required for delivery, plus explicitly authorized operators.

Public Actions output must not reveal:

- bucket name;
- object key;
- raw `sync_id`;
- draft ID or draft URL;
- manuscript/revision hash;
- queue page ID;
- raw ledger object contents;
- authentication state.

C-1 is redefined from "VM filesystem user ownership" to "cloud ledger and secret access boundary". OS-user evidence is no longer a C-1 requirement.

C-2 remains retention/backup/version-recovery evidence for the durable cloud ledger.

## 14. Workflow changes

`note-create-draft.yml` becomes a hosted-only workflow.

Remove:

- `start-cloud-vm` job;
- `[self-hosted, linux, x64, aiif-note-cloud]` runner selection;
- VM start/stop controller logic;
- runner registration assumptions;
- VM-local ledger path configuration;
- any test or guard whose only purpose is runner OS identity.

The hosted draft job must authenticate to GCP through Workload Identity Federation before ledger access.

The existing preflight may remain a separate hosted job or be folded into the hosted draft job if doing so does not weaken immutable handoff guarantees. Prefer the smaller design that keeps current tests easiest to preserve.

## 15. Failure semantics

- GCS unavailable: creation zero.
- CAS conflict: creation zero for the losing worker; re-read and reconcile.
- ledger record malformed/version-unsupported: creation zero.
- note auth invalid: creation zero if caught pre-mutation; otherwise no second-create authority after ambiguity.
- note creation ambiguous: `CREATION_UNKNOWN`; no automatic second creation.
- stable draft ID durable-write failure: queue mutation zero; no second creation.
- canonical verification failure: `VERIFICATION_BLOCKED`; no recreation.
- queue write ambiguous: readback first; no draft recreation.
- Actions result/summary failure after durable success: recover from ledger/readback.

## 16. Test requirements

All existing B01-B18 semantic cases remain required.

Replace SQLite-specific tests with cloud-ledger adapter tests covering:

- deterministic opaque object key;
- generation-match create-only semantics;
- generation-match state transition semantics;
- stale generation conflict;
- concurrent same-logical-delivery winner/loser behavior;
- malformed/unsupported ledger record fail-closed behavior;
- no unconditional overwrite path;
- privacy sentinel for public output.

Add hosted-only workflow/static tests proving:

- no `self-hosted` label in production note-create path;
- no GCE start/stop command in production note-create path;
- no VM-local ledger path in production note-create path;
- GCP WIF auth occurs before ledger access;
- Playwright/browser dependencies are installed on hosted runner;
- `NOTE_STORAGE_STATE_B64` is used only as ephemeral runtime input;
- no model call is added;
- no automatic public release path is added.

B01 live acceptance requires a single clean private-draft run ending in durable `QUEUE_CONFIRMED` with exact queue readback and zero model calls.

## 17. Rollout

1. implement a GCS-backed ledger adapter behind the existing semantic ledger interface;
2. preserve the existing SQLite adapter only for offline/reference tests until migration is complete, but remove it from production configuration;
3. convert `note-create-draft.yml` to hosted-only compute;
4. run focused ledger/runtime/workflow tests;
5. run full repository regression and falsification guards;
6. run one prepare-only production preflight;
7. run one bounded B01 private-draft live proof;
8. verify no duplicate draft, exact queue readback, durable `QUEUE_CONFIRMED`, and zero model calls;
9. close the VM/self-hosted operational dependency only after the hosted path is proven;
10. separately verify GCS IAM, retention, and recovery for C-1/C-2.

No merge to `main` occurs without explicit user `MERGE GO`.

## 18. Rollback

If hosted-only delivery fails:

- stop new note creation;
- preserve cloud ledger state;
- do not fall back automatically to the old self-hosted/VM path;
- do not clear active/ambiguous delivery records;
- fix and resume only from durable authority.

The legacy VM path must not become an implicit bypass around the cloud ledger.

## 19. Completion criteria

The hosted-only redesign is complete only when:

- production note draft creation uses GitHub-hosted runners only;
- no OS user, UID/GID, persistent home directory, systemd runner, or personal PC is required;
- B01-B18 pass at faithful production boundaries;
- B02-B07 retry cases keep total successful draft count at one;
- concurrent same-target execution cannot obtain two creation authorities;
- ephemeral runner destruction does not lose active delivery state;
- ambiguous creation never auto-recreates;
- stable draft identity and canonical verification remain intact;
- exact queue readback is required for `QUEUE_CONFIRMED`;
- private ledger/identity/authentication state never appears in public output;
- one bounded B01 live private-draft proof reaches `QUEUE_CONFIRMED` with zero model calls and zero public release;
- C-1/C-2 are evaluated against cloud IAM/retention, not OS-user ownership.
