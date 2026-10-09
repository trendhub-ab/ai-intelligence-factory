# Member Home Physical Host Migration — 2026-10-10

Status: **live physical move, post-move API proof, full regression, and production E2E complete; guest check pending**
Gemini/model calls: **0**
Daily: **not run**

## Objective

Restore the intended paid-member information architecture by making `AI Decision Intelligence｜会員ホーム` the physical parent of the existing canonical member database and monthly Decision Brief, without creating a second database or changing any canonical identity.

Target structure:

- `AI Decision Intelligence｜会員ホーム`
  - `会員限定Decision Brief｜2026年10月`
  - `AI・技術一覧｜判断DB`
    - existing member records remain children of the same database
  - `AI活用 判断メモ｜使う・試す・待つ・避ける` remains in place

## Canonical identities — unchanged

- Member home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- Canonical Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Canonical Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Decision Brief Page ID: `3d0479ff-dca9-81de-b614-fef528d2f32c`
- Pre-migration physical host Page ID: `3c5479ff-dca9-8178-867c-d9249a3ff5c8` (`mlflow/mlflow`)

No replacement DB may be created. `MEMBER_PRESENTATION_ALLOW_CREATE=false` remains mandatory.

## Gate 1 — production integration read proof before the move

Before moving anything, a dedicated branch-only GitHub Actions workflow used the same production secret as Member Presentation Sync: `NOTION_DECISION_INTELLIGENCE_API_KEY`.

Proof:
- Workflow run ID: `38003400357`
- Job ID: `114066553647`
- member home: **HTTP 200**
- canonical Database: **HTTP 200**
- canonical Data Source: **HTTP 200**
- Decision Brief: **HTTP 200**
- result: `READ_PROOF=PASS`

This satisfied the prerequisite that Run221 itself required before reconsidering physical placement under the member home.

## TDD contract before the move

A successor contract was written before the live move. Its initial RED run failed only because the repository still encoded the old Run221 state:

- RED workflow run ID: `38003610289`
- RED job ID: `114067212697`
- failures: current identity still used the old host; production workflow still pinned the old host; Run221 still declared itself current; successor migration record did not yet exist.

After the minimal contract changes, the same focused migration test became GREEN before the Notion move.

The successor contract keeps Run220 fail-closed identity protection and changes only the expected physical host:

- `API_HOST_PAGE_ID` is the member home ID `3c5479ff-dca9-8103-bff0-f2d5f408d35f`.
- bootstrap parent defaults to that same member home through the existing identity authority.
- Member Presentation Sync pins the same member-home host.
- Cross DB Contract Guard uses the same host for its live member check.
- canonical DB/Data Source IDs remain unchanged.
- no fallback by title and no automatic replacement DB creation are introduced.
- Run221 remains in the repository as superseded historical incident evidence.

## Live move — completed

The exact existing objects were physically moved under the member home in one migration operation:

1. canonical Database `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`;
2. Decision Brief page `3d0479ff-dca9-81de-b614-fef528d2f32c`.

No new database was created and no identity was replaced.

Post-move Notion reads confirmed:

- canonical Database parent = `AI Decision Intelligence｜会員ホーム`;
- Decision Brief parent = `AI Decision Intelligence｜会員ホーム`;
- Database ID unchanged: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`;
- Data Source ID unchanged: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`;
- Decision Brief Page ID unchanged: `3d0479ff-dca9-81de-b614-fef528d2f32c`.

## Data-integrity audit after the move

A direct read-only query of the canonical Data Source returned:

- rows: **240**;
- distinct `同期ID`: **240**;
- blank `同期ID`: **0**.

Representative record proof:

- record: `huggingface/datasets`;
- Page ID: `3d0479ff-dca9-8127-8b47-e0dccc7bb166`;
- ancestor chain: `AI Decision Intelligence｜会員ホーム` → `AI・技術一覧｜判断DB` → individual record;
- `同期ID`: `github:huggingface/datasets`;
- page body remained readable after the move.

## Gate 2 — production integration read proof after the move

The same GitHub Actions proof was rerun after physical placement changed.

Proof:
- Workflow run ID: `38003761092`
- post-move job ID: `114067929747`
- focused migration contract: **4 tests OK**
- member home: **HTTP 200**
- canonical Database: **HTTP 200**
- canonical Data Source: **HTTP 200**
- Decision Brief: **HTTP 200**
- result: `READ_PROOF=PASS`

The Run221 failure mode did not recur. **Rollback was not invoked.**

## Gate 3 — deterministic regression and synthetic Production smoke

A branch-only, zero-external-write regression workflow reproduced the current Integration Reconciliation CI contract: locked dependencies, compile, focused migration tests, Integration Stability Guard, repository falsification guard, full pytest, and synthetic Production smoke.

The first full run exposed three stale Run220 tests that still hard-coded the pre-migration `mlflow/mlflow` host. This was not a new production defect: **3,553 tests passed and the only three failures were the old physical-host expectation**. The canonical Database/Data Source IDs, no-fallback policy, and no-auto-create policy were already correct. The fix changed only the expected physical host in that historical cutover test to the member home.

Final fresh proof:
- Workflow run ID: `38004546138`
- Job ID: `114070207081`
- focused migration contract: **4/4 OK**
- Run221 successor/incident contract: **8/8 OK**
- Run220 canonical cutover contract: **7/7 OK**
- `INTEGRATION_STABILITY_GUARD=PASS`
- `REPOSITORY_FALSIFICATION_GUARD=PASS`
- full pytest: **3,556 passed, 0 failed**
- warning: **1 existing Pillow deprecation warning** unrelated to this migration
- synthetic Production smoke: **30/30 passed**
- synthetic critical failures: **0**
- production write isolation: **true**

Temporary regression/read-proof workflows and the RED trigger were removed from the branch after their evidence was captured. They are not part of the permanent production contract.

## Gate 4 — bounded production E2E after the move

A branch-only production E2E was run only after a fail-closed read-only preflight proved exact source/destination identity equality. It used the production Notion integrations, branch code, and the existing canonical objects. It did not call Gemini or another model.

Proof:
- Workflow run ID: `38005131012`
- Job ID: `114072048123`
- head SHA: `49e18246bf32813c20bb9f92c33b8e9b28fd33b9`
- canonical resolver: `created=false`, `canonical=true`, `auto_create_enabled=false`
- preflight: `source=240`, `destination=240`, exact `同期ID` set equality = **true**
- Presentation sync: `source_records=240`, `created=0`, `archived=0`, `duplicates_archived=0`, `updated=2`, `unchanged=238`, `zero_gemini_calls=true`
- post-Presentation audit: `rows=240`, `distinct_sync_ids=240`, `blank_sync_ids=0`
- body sync: `scanned_body_pages=240`, `total=240`, `unchanged=240`, `created=0`, `duplicates_removed=0`, `zero_gemini_calls=true`
- Decision Brief refresh: `source_records=240`, `top_count=5`, `important_change_count=0`, `zero_model_calls=true`
- final member home: **HTTP 200**
- final canonical Database: **HTTP 200**
- final canonical Data Source: **HTTP 200**
- final Decision Brief: **HTTP 200**
- result: `E2E_FINAL_API_PROOF=PASS`

The E2E preserved the 240-record identity contract and produced no create/archive/delete churn. The two Presentation updates were ordinary synchronization updates against existing canonical records, not identity replacement. All 240 page bodies were already current and therefore remained unchanged.

The branch-only E2E workflow was removed after this evidence was recorded. It is not part of the permanent production contract.

## Rollback contract

If a later pre-merge validation discovers that the production integration can no longer read the canonical Database/Data Source/Brief, rollback remains the fail-safe action before any main-branch change:

- move the same Database ID back to `3c5479ff-dca9-8178-867c-d9249a3ff5c8` (`mlflow/mlflow`);
- move the same Decision Brief ID back with it;
- do not create a new DB;
- do not change canonical IDs;
- re-run the read-only proof and require HTTP 200 after rollback;
- leave `main` unchanged.

## Remaining acceptance gates

Completed:

- physical parent = member home for canonical DB;
- physical parent = member home for Decision Brief;
- Database ID unchanged;
- Data Source ID unchanged;
- Decision Brief Page ID unchanged;
- member row count = **240**;
- distinct/blank `同期ID` audit = **240 / 0 blank**;
- representative individual page readable;
- GitHub Actions post-move read proof = HTTP 200 for all four targets;
- focused migration / Run220 / Run221 tests GREEN;
- full pytest = **3,556 passed**;
- Integration Stability Guard GREEN;
- Repository Falsification Guard GREEN;
- synthetic Production smoke = **30/30**;
- bounded production E2E = **PASS**;
- E2E source/member identity preflight = **240 / 240 exact match**;
- E2E Presentation post-audit = **240 rows / 240 distinct IDs / 0 blank IDs**;
- E2E body sync = **240/240 readable and unchanged**;
- E2E Decision Brief refresh = **PASS**;
- final E2E API proof = **HTTP 200 for all four targets**;
- temporary branch-only E2E workflow removed after evidence capture;
- PR #746 created as **Draft** against `main`;
- Gemini/model calls = **0**;
- Daily = **not run**.

Still required before completion:

- final guest-account navigation check succeeds: member home → Decision Brief → judgment DB/views → individual page → judgment memo;
- no merge before explicit `MERGE GO`.

The historical Run221 incident is not erased. This migration supersedes only its old-host-as-current-host rule after the live read, regression, integrity, and E2E gates above succeeded.
