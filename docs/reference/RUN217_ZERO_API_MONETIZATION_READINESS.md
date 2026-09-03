# Run217 — Zero-API Monetization Readiness

Date: 2026-09-03
Status: current paid-product operator contract
Gemini/model requests used for this run: **0**

## Purpose

Run217 moves the paid product from “technically synchronized” to “safe to hand to a paying member” without spending Gemini quota.

This is a product/onboarding baseline. It does **not** change the Run209 Production functional baseline or Run215 paid-member presentation logic.

## Sales funnel contract

**Free note article → membership LP → note membership → member Notion home → Decision DB / Digest**

Live LP checked on 2026-09-03:
- `https://note.com/trendhub_biz/n/ned673e381ef8`
- CTA `有料会員に参加する` resolves to the note membership surface.

The paid promise on the LP is:
- member-only Decision Intelligence DB
- member-only Digest
- continued addition of important AI / IT information
- primary-source / Evidence emphasis

Do not sell a benefit that is not actually available to the member.

## Canonical member entrypoint

New paying members must be invited to / directed to the **member home**, not to an internal source record and not to the legacy presentation database.

### Member home

- Title: `AI Intelligence｜会員ホーム`
- Page ID: `3d0479ff-dca9-819e-9da0-c951225de6b3`
- URL: `https://app.notion.com/p/3d0479ffdca9819e9da0c951225de6b3`

The home contains three linked views over the current member presentation data source:

1. `① 今すぐ見る3件`
   - filter: `注目順位 <= 3`
   - sorted by `注目順位 ASC`
   - intended as the default first view for a time-poor member
2. `② 実務判断だけ`
   - filter: `分類 = 実務判断`
   - sorted by `判断スコア DESC`
3. `③ すべての判断DB`
   - full current member inventory
   - sorted by `判断スコア DESC`

Only member-relevant properties should be displayed in these linked views. Internal sync identifiers are not part of the default member surface.

## Current authoritative member presentation DB

- Database ID: `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1`
- Data source ID: `d1461b6f-0940-4bf9-803a-6686a37c4ba2`
- Title: `AI・技術一覧｜判断DB`

Audit snapshot on 2026-09-03:
- rows: **206**
- blank `次にやること`: **0**
- distinct `次にやること`: **206**
- generic `今回の話題`: **0**
- ADOPT: 44
- TEST: 72
- WATCH: 82
- AVOID: 8
- 実務判断: 139
- Deep Tech: 62
- 参考資料: 5
- oldest `最終確認日`: 2026-08-22
- latest `最終確認日`: 2026-09-02

This is the only presentation data source that should be used for current paid-member onboarding.

## Legacy duplicate DB — do not onboard members here

A second older database existed under the `mlflow/mlflow` source record.

- Database ID: `9430d2a5-b9ce-423a-b76e-d9214f3f6204`
- Data source ID: `ec2ac2b3-89b6-4242-89b9-e94060826fca`
- Audit snapshot: 100 rows / only 38 distinct `次にやること`

Run217 renamed it to:

`⚠️ 旧版・使用禁止｜AI・技術一覧（100件・更新停止）`

It is retained rather than deleted for safety/audit purposes. Do not invite members to it and do not use it as a current product URL.

## Digest fulfillment contract

The LP explicitly sells a member-only Digest. Automated Digest generation is not currently relied upon for product fulfillment while the normal Daily schedule remains PAUSED.

Run217 created the first current member Digest from already-authoritative DB content only:

- Title: `会員限定Digest｜2026年9月 初回版`
- Page ID: `3d0479ff-dca9-81de-b614-fef528d2f32c`
- URL: `https://app.notion.com/p/3d0479ffdca981deb614fef528d2f32c`
- parent: member home
- Gemini/model requests: **0**

The member home links to this Digest near the top.

Until automated Digest delivery is deliberately re-enabled and validated, the paid service must still receive at least a human/zero-model current-DB Digest for each promised monthly cycle. Do not silently advertise Digest while delivering none.

## First-view editorial contract

The current `今すぐ見る3件` are intentionally diverse in decision utility rather than simply the highest raw scores:

1. `langgenius/dify` — ADOPT 91
2. `Mintplex-Labs/anything-llm` — TEST 82
3. `NVIDIA-NeMo/Guardrails` — ADOPT 80

They cover:
- common AI application platform
- internal-document AI trial
- production AI safety / guardrails

The member should be able to understand each item through:

`これは何？ → いまの判断 → なぜ今見る？ → 次にやること`

## Important-change semantics

As of the Run217 audit, `今月の重要変化 = true` is 0 records.

Do **not** convert the top-three priority list into `今月の重要変化` merely to make the product look active. Priority and observed change are different concepts. Mark important change only when the underlying product/state actually changed under the existing current-authority rules.

## Onboarding operator checklist

For each paid member:

1. Confirm active note membership using the existing human verification process.
2. Invite the member to `AI Intelligence｜会員ホーム`.
3. Do not send the `mlflow/mlflow` internal source page as the product entrypoint.
4. Do not send the legacy 100-row database.
5. Confirm the member can open `① 今すぐ見る3件` and the current Digest.
6. If access fails, fix Notion sharing before considering onboarding complete.

## Non-goals / safety

Run217 does not:
- call Gemini or any model API
- change Decision score or judgment
- weaken Evidence / Fact gates
- change article-generation logic
- resume Daily
- enable public note auto-release
- invent related-article URLs
- mark fake “important changes”
- delete the legacy DB

The next business milestone is not another architecture rewrite. It is an actual paid conversion and then measuring activation / retention against this member-home experience.
