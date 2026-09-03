# Run220 — Canonical Member DB Cutover

Date: 2026-09-03  
Status: **current paid-member database destination contract; physical hosting clarified by Run221**  
Gemini/model requests used for this run: **0**

## Why this run exists

Run219 correctly generated human-language member pages, but the production Member Presentation workflow provisioned a new API-visible database because the prior customer-facing database was not resolved by the internal Notion integration. This created a split state: the workflow wrote to one database while the member home still linked to another.

Run220 removes that ambiguity. The paid member product has exactly one canonical presentation database, and the workflow must fail closed if it cannot write to it.

Run221 later proved that the **customer-facing member home and the physical API host must remain separate under the current Notion sharing setup**. Run220 remains authoritative for the canonical Database/Data Source IDs; Run221 is authoritative for physical hosting.

## Canonical member destination

- Member home: `AI Decision Intelligence｜会員ホーム`
- Member home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- Canonical presentation Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Canonical presentation Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Canonical DB title: `AI・技術一覧｜判断DB`
- Current physical API host Page ID: `3c5479ff-dca9-8178-867c-d9249a3ff5c8`

The member home points to the canonical Run220 data through member-facing views/links. **Do not infer physical parentage from the member-navigation hierarchy.**

The canonical DB is physically hosted under the API-accessible host defined by Run221 so GitHub Actions can continue to read and update it. Moving the DB directly under the member home without first sharing that parent with the Actions Notion integration was observed to cause HTTP 404 and is therefore not the current contract.

## Old presentation database

The former customer-facing presentation database is retained only as audit history:

- Old Database ID: `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1`
- Old Data Source ID: `d1461b6f-0940-4bf9-803a-6686a37c4ba2`
- Current title: `⚠️ 旧版・使用禁止｜AI・技術一覧（Run219前）`
- Parent: `【旧・統合済み】AI Intelligence｜会員ホーム`

It must not be used for member onboarding, current views, workflow writes, LP links, or operator instructions.

The still-older 100-row legacy data source `ec2ac2b3-89b6-4242-89b9-e94060826fca` remains legacy/audit-only as well.

## Workflow contract

`provision_member_presentation_db.py` and `.github/workflows/member-presentation-sync.yml` must use the canonical IDs above.

Normal Production behavior:

1. Verify the configured canonical Data Source is readable.
2. Verify its parent Database ID matches the configured canonical Database ID.
3. Verify the title is the expected member DB title.
4. Verify the canonical Database remains under the Run221 API-accessible physical host.
5. Export those exact IDs through `GITHUB_ENV`.
6. Run Run219 presentation/body sync against those exact IDs.

If any verification fails, **fail closed**.

The normal workflow must not:
- fall back to another same-title database
- create a new presentation database
- silently switch destinations
- write to the old Run219-pre-cutover DB
- physically relocate the canonical DB as part of normal sync

Automatic creation is disabled by default (`MEMBER_PRESENTATION_ALLOW_CREATE=false`). Creation remains code-level bootstrap capability only and is not the normal Production path.

## Member-home view cutover

The canonical member home was switched from the old Data Source to `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`.

Current user-facing views include:
- `まず見る3件`
- `ほかのおすすめ`
- `すべてから探す`
- `分野から探す`
- `導入を考えてよいもの`
- `まず小さく試したいもの`
- `もう少し様子を見たいもの`
- `今は選ばない方がよいもの`
- `まとめて比べる`
- `最近、評価が上がったもの`
- `これから注目したい新技術`
- `前と判断が大きく変わったもの`
- `スマホで見る`

The home uses PC-first links/views to the canonical Run220 Data Source. Mobile remains secondary.

## Run219 language contract preserved

Run220 changes only destination authority and navigation. It does not change the Run219 human-language presentation rules.

Verified canonical Dify page uses:
- `このAI・技術をどう見る？`
- `いま、どうする？`
- `そう判断した理由`
- `気をつけたいこと`
- `こんな使い方に向いています`
- `こんな使い方には向きません`
- `確認に使った公式・一次情報`

Body summary hides ADOPT/TEST/WATCH/AVOID codes and presents the Japanese action meaning instead.

## Run221 hosting clarification

Post-merge Run220 validation proved the hosting distinction directly:

- moving canonical DB `b2787ee0-5b58-4ca7-b4eb-774f60237f1f` beneath the member home made the Actions integration resolve it as HTTP 404;
- Run220 failed closed and created no fallback DB;
- moving the same DB back to API host `3c5479ff-dca9-8178-867c-d9249a3ff5c8` restored access;
- rerunning the same main SHA succeeded with `created: False`, 206 unchanged records and `zero_gemini_calls=true`.

Full hosting contract: `docs/reference/RUN221_MEMBER_DB_HOST_ISOLATION.md`.

## Safety / non-goals

Run220 / Run221 do not:
- call Gemini/model APIs
- change Decision scores or judgment values
- change Evidence authority
- change article generation
- resume Daily
- enable public note auto-release
- infer or fabricate data

Daily remains PAUSED and public note release remains human-only.
