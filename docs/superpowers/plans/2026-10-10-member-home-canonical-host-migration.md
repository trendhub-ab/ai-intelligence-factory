# Member Home Canonical Host Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the canonical paid-member DB and monthly Decision Brief under `AI Decision Intelligence｜会員ホーム` while preserving IDs, fail-closed sync, and zero-model operation.

**Architecture:** First prove the production GitHub Actions Notion integration can read the member home. Then change only the physical-host contract from the Run221 host to the member home, preserving the canonical DB/Data Source identities and creation ban. Coordinate the external Notion move with the final merge and verify/rollback by identity and row-count evidence.

**Tech Stack:** Python 3.11, unittest/pytest, GitHub Actions, Notion Public API 2026-03-11.

**Spec:** `docs/superpowers/specs/2026-10-10-member-home-canonical-host-migration-design.md`

## Global Constraints

- Member home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`.
- Canonical Database ID remains `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`.
- Canonical Data Source ID remains `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`.
- Monthly Decision Brief Page ID remains `3d0479ff-dca9-81de-b614-fef528d2f32c`.
- `MEMBER_PRESENTATION_ALLOW_CREATE=false` remains mandatory in production.
- No model calls, Daily, Fresh, schema changes, ranking changes, or copy changes.
- No replacement database may be created.
- Merge requires explicit `MERGE GO`.

## Review Focus

- Member-home permission exists for the production integration before any physical move.
- Host mismatch still fails closed before writes.
- Canonical DB/Data Source IDs cannot drift during the host migration.
- Bootstrap parent follows the new member-home host without enabling creation in production.
- Post-cutover row count and distinct nonblank `同期ID` count stay at 240.

---

### Task 1: Read-only production integration access proof

**Files:**
- Create temporarily: `.github/workflows/member-home-access-probe.yml`

**Interfaces:**
- Consumes: production secret `NOTION_DECISION_INTELLIGENCE_API_KEY` already used by Member Presentation Sync.
- Produces: GitHub Actions evidence that `GET /v1/pages/3c5479ff-dca9-8103-bff0-f2d5f408d35f` returns HTTP 200 without writes.

- [ ] **Step 1: Add a PR-only read-only probe workflow**

The workflow must perform one GET to the member-home page with `Notion-Version: 2026-03-11`, print only HTTP status plus a fixed PASS marker, and fail unless status is 200. It must contain no POST/PATCH/DELETE and no model secret.

- [ ] **Step 2: Open a draft PR and observe the probe**

Expected: `MEMBER_HOME_API_ACCESS=PASS` and HTTP 200.

- [ ] **Step 3: If the probe fails**

Stop before physical migration. The required operator action is to share `AI Decision Intelligence｜会員ホーム` with the `AI Intelligence Factory TEST` integration, then rerun the probe.

- [ ] **Step 4: Remove the temporary probe workflow after proof is captured**

Expected: the final production diff does not retain an unnecessary standalone probe workflow.

### Task 2: RED — define the new member-home physical-host contract

**Files:**
- Modify: `tests/test_run221_member_db_host_isolation.py`
- Create: `tests/test_member_home_canonical_host_migration.py`

**Interfaces:**
- Consumes: existing `member_presentation_identity.py`, `provision_member_presentation_db.py`, workflow pins, Run221 historical doc.
- Produces: tests that require member home to be the canonical physical parent while preserving fail-closed checks and canonical IDs.

- [ ] **Step 1: Write failing tests**

Tests must assert:
- default API host equals member-home Page ID;
- bootstrap parent equals member home;
- production workflow pins the member-home Page ID;
- a database physically under the former Run221 host fails closed;
- a database physically under member home passes host verification;
- canonical DB/Data Source IDs and `ALLOW_CREATE=false` remain unchanged;
- Run221 is marked superseded and a new migration reference exists.

- [ ] **Step 2: Trigger CI and verify RED**

Expected: failures are specifically caused by the old Run221 host still being configured/documented.

### Task 3: GREEN — minimal host-contract implementation

**Files:**
- Modify: `member_presentation_identity.py`
- Modify: `provision_member_presentation_db.py`
- Modify: `.github/workflows/member-presentation-sync.yml`
- Modify: `tests/test_run221_member_db_host_isolation.py`
- Create/Modify: `tests/test_member_home_canonical_host_migration.py`
- Modify: `docs/reference/RUN221_MEMBER_DB_HOST_ISOLATION.md`
- Create: `docs/reference/MEMBER_HOME_CANONICAL_HOST_MIGRATION.md`

**Interfaces:**
- Consumes: Task 2 RED contract.
- Produces: member-home host pin used consistently by provisioning and workflow.

- [ ] **Step 1: Change the default physical host to member home**

Set `API_HOST_PAGE_ID` to `3c5479ff-dca9-8103-bff0-f2d5f408d35f`. Keep DB/Data Source IDs unchanged.

- [ ] **Step 2: Update operator/error wording**

Remove instructions that require linked-view isolation as the current architecture. Preserve fail-closed semantics.

- [ ] **Step 3: Update production workflow pin**

Set `MEMBER_PRESENTATION_API_HOST_PAGE_ID` to the member-home Page ID. Keep `MEMBER_PRESENTATION_ALLOW_CREATE: 'false'` and no model key.

- [ ] **Step 4: Supersede Run221 and add migration reference**

Record the former host, new host, unchanged IDs, pre-cutover integrity baseline (240/240/0), access-proof evidence, rollback path, and zero-model/no-Daily constraints.

- [ ] **Step 5: Trigger focused/full CI**

Expected: focused tests PASS; full pytest PASS; repository guards PASS; synthetic smoke 30/30 or current canonical equivalent.

### Task 4: Prepare coordinated cutover

**Files:**
- No additional production code unless verification exposes a defect.

**Interfaces:**
- Consumes: Task 3 verified branch and explicit `MERGE GO`.
- Produces: production main whose host contract matches the immediately-following Notion move.

- [ ] **Step 1: Open/update PR with all verification evidence**

Expected: PR is mergeable and all required checks are green.

- [ ] **Step 2: Stop for explicit `MERGE GO`**

No production merge or physical Notion move before authorization.

### Task 5: Production cutover and rollback proof

**Files:**
- External Notion structure only; follow-up documentation commit only if observed evidence differs from prewritten expectations.

**Interfaces:**
- Consumes: merged host contract and Notion move capability.
- Produces: the requested physical hierarchy and live sync proof.

- [ ] **Step 1: Move canonical DB and Decision Brief under member home**

Move exactly Database ID `b2787ee0-5b58-4ca7-b4eb-774f60237f1f` and Brief Page ID `3d0479ff-dca9-81de-b614-fef528d2f32c` to parent Page ID `3c5479ff-dca9-8103-bff0-f2d5f408d35f`. Do not move the judgment memo; it is already there.

- [ ] **Step 2: Verify identity and integrity immediately**

Expected:
- DB parent = member home;
- Brief parent = member home;
- memo parent = member home;
- Database/Data Source/Brief IDs unchanged;
- rows = 240;
- distinct `同期ID` = 240;
- blank `同期ID` = 0.

- [ ] **Step 3: Verify production API and Member Presentation Sync**

Expected: canonical resolution succeeds, presentation/body/monthly Brief sync succeeds, zero model calls, no Daily run.

- [ ] **Step 4: Roll back if any API-readability check fails**

Move the same DB and Brief IDs back to former host `3c5479ff-dca9-8178-867c-d9249a3ff5c8`; create nothing.
