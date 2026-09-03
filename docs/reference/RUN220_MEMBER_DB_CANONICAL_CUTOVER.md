# Run220 — Canonical Member DB Cutover

Date: 2026-09-03  
Status: **current paid-member database destination contract**  
Gemini/model requests used for this run: **0**

## Why this run exists

Run219 correctly generated human-language member pages, but the production Member Presentation workflow provisioned a new API-visible database because the prior customer-facing database was not resolved by the internal Notion integration. This created a split state: the workflow wrote to one database while the member home still linked to another.

Run220 removes that ambiguity. The paid member product has exactly one canonical presentation database, and the workflow must fail closed if it cannot write to it.

## Canonical member destination

- Member home: `AI Decision Intelligence｜会員ホーム`
- Member home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- Canonical presentation Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Canonical presentation Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Canonical DB title: `AI・技術一覧｜判断DB`

The database was moved under the canonical member home, so normal item breadcrumbs are:

`AI Decision Intelligence｜会員ホーム → AI・技術一覧｜判断DB → individual item`

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
4. Export those exact IDs through `GITHUB_ENV`.
5. Run Run219 presentation/body sync against those exact IDs.

If any verification fails, **fail closed**.

The normal workflow must not:
- fall back to another same-title database
- create a new presentation database
- silently switch destinations
- write to the old Run219-pre-cutover DB

Automatic creation is disabled by default (`MEMBER_PRESENTATION_ALLOW_CREATE=false`). Creation remains code-level bootstrap capability only and is not the normal Production path.

## Member-home view cutover

The canonical member home was switched from the old Data Source to `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`.

Current user-facing views are rebuilt on the canonical DB, including:
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

The home uses PC-first links to these views. Mobile remains secondary.

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

## Safety / non-goals

Run220 does not:
- call Gemini/model APIs
- change Decision scores or judgment values
- change Evidence authority
- change article generation
- resume Daily
- enable public note auto-release
- infer or fabricate data

Daily remains PAUSED and public note release remains human-only.
