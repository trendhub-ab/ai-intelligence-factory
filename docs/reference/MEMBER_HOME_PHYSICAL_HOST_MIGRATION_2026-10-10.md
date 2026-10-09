# Member Home Physical Host Migration — 2026-10-10

Status: **pre-move contract staged; live move and post-move proof pending**  
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

## Gate 1 — production integration read proof

Before moving anything, a dedicated branch-only GitHub Actions workflow used the same production secret as Member Presentation Sync: `NOTION_DECISION_INTELLIGENCE_API_KEY`.

Proof:
- Workflow run ID: `38003400357`
- Job ID: `114066553647`
- member home: **HTTP 200**
- canonical Database: **HTTP 200**
- canonical Data Source: **HTTP 200**
- Decision Brief: **HTTP 200**
- result: `READ_PROOF=PASS`

This satisfies the prerequisite that Run221 itself required before reconsidering physical placement under the member home.

## Code contract staged before the move

The successor contract keeps Run220 fail-closed identity protection and changes only the expected physical host:

- `API_HOST_PAGE_ID` becomes the member home ID `3c5479ff-dca9-8103-bff0-f2d5f408d35f`.
- bootstrap parent defaults to that same member home through the existing identity authority.
- Member Presentation Sync pins the same member-home host.
- canonical DB/Data Source IDs remain unchanged.
- no fallback by title and no automatic replacement DB creation are introduced.
- Run221 remains in the repository as superseded historical incident evidence.

## Live migration sequence

1. Move the same canonical Database `b2787ee0-5b58-4ca7-b4eb-774f60237f1f` under the member home.
2. Move the same Decision Brief page `3d0479ff-dca9-81de-b614-fef528d2f32c` under the member home.
3. Re-fetch both objects and verify their parent is the member home.
4. Verify the canonical Data Source ID is still `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`.
5. Verify row count, distinct `同期ID`, blank `同期ID`, and representative member pages.
6. Re-run the GitHub Actions read-only proof after the move.
7. Only if all API checks stay HTTP 200 may the successor contract proceed to PR/full regression.

## Rollback

If the post-move GitHub Actions proof returns HTTP 404 or otherwise cannot read the canonical Database/Data Source/Brief, perform an immediate **rollback** before any main-branch change:

- move the same Database ID back to `3c5479ff-dca9-8178-867c-d9249a3ff5c8` (`mlflow/mlflow`);
- move the same Decision Brief ID back with it;
- do not create a new DB;
- do not change canonical IDs;
- re-run the read-only proof and require HTTP 200 after rollback;
- leave `main` unchanged.

## Post-move acceptance gates

The migration is not complete until all of the following are evidenced:

- physical parent = member home for canonical DB;
- physical parent = member home for Decision Brief;
- Database ID unchanged;
- Data Source ID unchanged;
- Decision Brief Page ID unchanged;
- member row count preserved at the actual pre-move count;
- distinct/blank `同期ID` audit passes;
- representative individual pages remain readable;
- GitHub Actions post-move read proof = HTTP 200 for all four targets;
- focused migration tests GREEN;
- full pytest / guards / synthetic smoke GREEN;
- Member Presentation Sync E2E succeeds with Gemini/model calls 0 and Daily not run;
- final guest-account navigation check succeeds.

The historical Run221 incident is not erased. This migration supersedes only its old-host-as-current-host rule after all live acceptance gates pass.
