# Run221 — Member DB API Host Isolation

Date: 2026-09-04  
Status: **current paid-member physical hosting contract**  
Gemini/model requests used for this run: **0**

## Why this run exists

Run220 correctly pinned the paid-member product to one canonical Presentation DB and disabled silent fallback / auto-creation. During post-merge validation, a separate Notion permission boundary was discovered:

- the canonical DB was physically moved under the customer-facing member home to improve breadcrumbs;
- the GitHub Actions Notion integration then received HTTP 404 when resolving the same canonical Data Source;
- Run220 correctly failed closed and created no replacement database;
- moving the exact same canonical DB back to the API-accessible host restored access immediately;
- rerunning the exact same main SHA then completed successfully with the same canonical IDs.

This proves that **customer navigation and physical API hosting are different concerns** in the current Notion permission setup.

## Current architecture

### Customer-facing product surface

- Member home: `AI Decision Intelligence｜会員ホーム`
- Member home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- PC-first member navigation is owned by Run218.
- Plain-Japanese member body language is owned by Run219.
- The member home exposes the canonical Data Source through member-facing links / linked views.

### Canonical product data

- Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Title: `AI・技術一覧｜判断DB`

### Physical API host

- Physical host Page ID: `3c5479ff-dca9-8178-867c-d9249a3ff5c8`
- Current host title: `mlflow/mlflow`

The physical host is an implementation/access boundary, **not the member onboarding destination**. The canonical DB must remain API-readable there while the current GitHub Actions Notion integration depends on inherited access from that host.

The canonical DB **must not be physically moved under the member home** unless the GitHub Actions Notion integration has first been explicitly granted and verified access to that parent. The current connector surface cannot grant that sharing permission programmatically.

## Run220 post-merge evidence

Main SHA:
- `a3eecf70f64ddea46525b2e0225e1d94ea822b09`

Member Presentation Sync:
- Run ID: `33771347577`

Attempt 1:
- Job ID: `100702070417`
- canonical Data Source resolution: **FAIL**
- error: HTTP 404
- fallback DB selection: **0**
- new DB creation: **0**

The failure occurred after the canonical DB had been moved beneath the member home.

The same Database/Data Source were then moved back to physical API host `3c5479ff-dca9-8178-867c-d9249a3ff5c8`.

Attempt 2, same main SHA:
- Job ID: `100702646385`
- canonical Data Source resolution: **SUCCESS**
- presentation sync: **SUCCESS**
- body sync: **SUCCESS**
- `created: False`
- canonical DB: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- canonical Data Source: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
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

The Dify member page still uses the Run219 plain-Japanese headings and content after recovery.

## Production contract

`provision_member_presentation_db.py` must verify all of the following before writes:

1. configured canonical Data Source is readable;
2. its parent Database ID equals the configured canonical Database ID;
3. title is the expected member DB title;
4. canonical Database is readable;
5. its physical parent page equals `MEMBER_PRESENTATION_API_HOST_PAGE_ID`;
6. any mismatch fails closed before member writes.

Production workflow pins:

- `MEMBER_PRESENTATION_CANONICAL_DATABASE_ID=b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- `MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID=7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- `MEMBER_PRESENTATION_API_HOST_PAGE_ID=3c5479ff-dca9-8178-867c-d9249a3ff5c8`
- `MEMBER_PRESENTATION_ALLOW_CREATE=false`

The explicit bootstrap parent also defaults to the API host rather than the member home.

## Member UX contract

The physical host must not be treated as the product home.

The member experience remains:

**note membership → AI Decision Intelligence｜会員ホーム → member-facing linked views / records**

Do not put `mlflow/mlflow` into onboarding copy, LP copy, or operator instructions to members.

Because the current automation integration needs the API host for inherited access, a completely clean full-page Notion breadcrumb cannot be guaranteed by physically moving the database. If clean full-page breadcrumbs become commercially important, first manually share the canonical member-home parent with the GitHub Actions Notion integration, verify API readability, and only then consider a physical move in a separate migration with rollback proof.

Until that permission migration is explicitly completed, **availability and automatic synchronization take priority over cosmetic physical placement**. Member-facing navigation should use linked views and plain-language pages to isolate the implementation host as much as possible.

## Safety / non-goals

Run221 does not:
- create a new member database;
- change the canonical DB/Data Source IDs;
- change Decision scores, judgments, Evidence, or Fact authority;
- change Run219 member copy;
- enable Gemini/model calls in derived member sync;
- resume Daily;
- enable public note auto-release;
- weaken Run220 fail-closed behavior.

Daily remains PAUSED. Public note release remains human-only.
