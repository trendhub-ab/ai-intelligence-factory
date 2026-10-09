# Run221 — Member DB API Host Isolation

Date: 2026-09-04  
Status: **superseded as the current hosting contract; retained as historical incident evidence**
Superseded by: `MEMBER_HOME_PHYSICAL_HOST_MIGRATION_2026-10-10.md` after its live migration gates pass
Gemini/model requests used for this run: **0**

## Why this run existed

Run220 pinned the paid-member product to one canonical Presentation DB and disabled silent fallback / auto-creation. During post-merge validation in September 2026, a Notion permission boundary was observed:

- the canonical DB was physically moved under the customer-facing member home;
- the GitHub Actions Notion integration then received HTTP 404 when resolving the same canonical Data Source;
- Run220 failed closed and created no replacement database;
- moving the exact same canonical DB back to the API-accessible host restored access;
- rerunning the exact same main SHA completed successfully with the same canonical IDs.

Run221 therefore separated customer navigation from physical API hosting until the member-home parent itself could be explicitly proven readable by the production GitHub Actions integration.

## Historical architecture protected by Run221

### Customer-facing product surface

- Member home: `AI Decision Intelligence｜会員ホーム`
- Member home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`

### Canonical product data

- Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Title: `AI・技術一覧｜判断DB`

### Historical physical API host

- Physical host Page ID: `3c5479ff-dca9-8178-867c-d9249a3ff5c8`
- Host title: `mlflow/mlflow`

Under Run221, the canonical DB had to remain under this host because moving it to the member home had produced HTTP 404. The member home exposed the canonical Data Source with member-facing links / linked views instead.

## Run220 post-merge evidence retained by Run221

Main SHA:
- `a3eecf70f64ddea46525b2e0225e1d94ea822b09`

Member Presentation Sync:
- Run ID: `33771347577`

Attempt 1 after the DB was moved beneath the member home:
- Job ID: `100702070417`
- canonical Data Source resolution: **FAIL**
- error: **HTTP 404**
- fallback DB selection: **0**
- new DB creation: **0**

After moving the same Database/Data Source back to physical API host `3c5479ff-dca9-8178-867c-d9249a3ff5c8`:

Attempt 2, same main SHA:
- Job ID: `100702646385`
- canonical Data Source resolution: **SUCCESS**
- presentation sync: **SUCCESS**
- body sync: **SUCCESS**
- `created: False`
- source records: **206**
- presentation updated: **0**
- presentation unchanged: **206**
- body total: **206**
- body unchanged: **206**
- `zero_gemini_calls=true`

Direct Notion audit after recovery:
- rows: **206**
- distinct `同期ID`: **206**
- blank `同期ID`: **0**

## Why Run221 is now superseded

On 2026-10-10, before any physical move, a dedicated GitHub Actions read-only proof used the same production secret `NOTION_DECISION_INTELLIGENCE_API_KEY` and returned HTTP 200 for the member home, canonical Database, canonical Data Source, and Decision Brief. The exact proof identifiers and the new rollback contract are recorded in `MEMBER_HOME_PHYSICAL_HOST_MIGRATION_2026-10-10.md`.

This changes the premise that forced host isolation: the member-home parent is now API-readable by the production integration. The old incident remains important evidence, but the old `mlflow/mlflow` parent is no longer intended to be the current physical host once the live migration and post-move API proof succeed.

## Historical safety contract

Run221 required `provision_member_presentation_db.py` to fail closed unless:

1. the configured canonical Data Source was readable;
2. its parent Database ID matched the configured canonical Database ID;
3. the title matched the expected member DB title;
4. the canonical Database was readable;
5. its physical parent matched `MEMBER_PRESENTATION_API_HOST_PAGE_ID`;
6. any mismatch stopped before member writes.

Those fail-closed properties remain valid. The successor migration changes only the expected physical parent from the historical `mlflow/mlflow` page to the canonical member home after live proof.

## Safety / non-goals

Superseding Run221 does not authorize:
- creating a new member database;
- changing the canonical Database/Data Source IDs;
- changing Decision scores, judgments, Evidence, or Fact authority;
- enabling Gemini/model calls in derived member sync;
- resuming Daily;
- enabling public note auto-release;
- weakening Run220 no-fallback / no-auto-create behavior.

Run221 is preserved as the record of the September 2026 HTTP 404 incident. It must not be deleted or rewritten as though that incident never occurred.
