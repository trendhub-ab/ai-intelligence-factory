# Member Home Canonical Host Migration Design

Date: 2026-10-10
Status: approved for execution
Base main: `cc8f45be86bf85f0755d57e6cae69d9594bee444`

## Goal

Restore the paid-member Notion product to one clean physical hierarchy without changing canonical identities:

```text
AI Decision Intelligence｜会員ホーム
├─ 会員限定Decision Brief
├─ AI・技術一覧｜判断DB
│  └─ 個別240件
└─ AI活用 判断メモ
```

## Canonical identities

- Member home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- Member DB Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Member DB Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Monthly Decision Brief Page ID: `3d0479ff-dca9-81de-b614-fef528d2f32c`
- Judgment memo Page ID: `3d3479ff-dca9-8119-b0d8-c014b068fe82`
- Former Run221 API host Page ID: `3c5479ff-dca9-8178-867c-d9249a3ff5c8`

The database and data-source IDs must not change. No replacement DB may be created.

## Preconditions

1. The GitHub Actions Notion integration must prove read access to the member-home page using the production `NOTION_DECISION_INTELLIGENCE_API_KEY`.
2. The proof must be read-only: HTTP GET only; no Notion writes, no model calls, no Daily run.
3. Current live database integrity must be captured before cutover: 240 rows, 240 distinct nonblank `同期ID` values.

## Production contract after cutover

`provision_member_presentation_db.py` must continue to fail closed and verify:

1. the configured canonical Data Source is readable;
2. its parent Database ID equals the configured canonical Database ID;
3. the title is `AI・技術一覧｜判断DB`;
4. the canonical Database is readable;
5. its physical parent page equals the member-home Page ID;
6. any mismatch fails before member writes;
7. automatic DB creation remains disabled.

The bootstrap parent defaults to the member home after migration.

## Cutover sequence

1. Prove member-home API readability with the production GitHub Actions integration.
2. Implement the new host contract on an isolated branch using TDD; keep canonical IDs and fail-closed behavior unchanged.
3. Run focused tests, full pytest, repository guards, and synthetic smoke. Open a PR but do not merge without explicit `MERGE GO`.
4. At coordinated cutover, merge the verified contract and immediately move the canonical DB and monthly Decision Brief under the member home. The judgment memo already lives there and is not moved.
5. Verify the same DB/Data Source/Brief IDs, 240 rows, 240 distinct nonblank `同期ID` values, and API readability after the move.
6. Run Member Presentation Sync and prove end-to-end success with zero model calls and no Daily run.

## Rollback

If the post-move API check fails or the canonical Data Source becomes unreadable, move the same Database ID and Decision Brief Page ID back to former Run221 host `3c5479ff-dca9-8178-867c-d9249a3ff5c8`. Never create a replacement database. Record the failure and keep production fail-closed.

## Documentation

Run221 remains historical evidence but must be marked superseded by this migration after cutover. A new reference document records the new physical-host contract and rollback proof.

## Non-goals

- No changes to Decision scores, judgments, Evidence, Fact authority, ranking, or member copy.
- No schema change.
- No Gemini/OpenAI/model request.
- No Daily or Fresh execution.
- No note publication change.
- No new member database.
