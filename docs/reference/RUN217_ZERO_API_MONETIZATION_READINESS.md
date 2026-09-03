# Run217 — Zero-API Monetization Readiness

Date: 2026-09-03  
Status: **historical commerce-readiness baseline; member-home navigation superseded by Run218**  
Gemini/model requests used for this run: **0**

## Purpose and correction

Run217 validated the paid-product inventory, legacy-database quarantine, LP/Digest fulfillment, and zero-model onboarding readiness. Those findings remain valid.

However, the Run217 audit created a parallel page named `AI Intelligence｜会員ホーム` and incorrectly documented it as the canonical member entrypoint. The workspace already had the actual customer-facing home `AI Decision Intelligence｜会員ホーム`. This navigation/UI mistake was found and corrected in Run218.

**Current member-home authority is therefore Run218, not the Run217-created page.**

- Current canonical home: `AI Decision Intelligence｜会員ホーム`
- Current canonical Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- Current operator contract: `docs/reference/RUN218_MEMBER_UX_RECONCILIATION.md`

The Run217-created page is retained only as an explicit superseded artifact:

- Old Page ID: `3d0479ff-dca9-819e-9da0-c951225de6b3`
- Current title: `【旧・統合済み】AI Intelligence｜会員ホーム`
- It must **not** be used for new-member invitations, bookmarks, LP links, or operator instructions.

## Sales funnel contract retained from Run217

**Free note article → membership LP → note membership → canonical member Notion home → Decision DB / Digest**

Live LP checked on 2026-09-03:
- `https://note.com/trendhub_biz/n/ned673e381ef8`
- CTA `有料会員に参加する` resolved to the note membership surface.

The paid promise remains:
- member-only Decision Intelligence DB
- member-only Digest
- continued addition of important AI / IT information
- primary-source / Evidence emphasis

Do not sell a benefit that is not actually available to the member.

## Current authoritative member presentation DB

These Run217 inventory findings remain authoritative unless a later live audit supersedes the snapshot values.

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

Run218 moved this current DB under the real canonical member home so customer-facing breadcrumbs no longer traverse the internal `mlflow/mlflow` source record.

## Legacy duplicate DB — do not onboard members here

The older duplicate remains quarantined:

- Database ID: `9430d2a5-b9ce-423a-b76e-d9214f3f6204`
- Data source ID: `ec2ac2b3-89b6-4242-89b9-e94060826fca`
- Audit snapshot: 100 rows / only 38 distinct `次にやること`
- Title: `⚠️ 旧版・使用禁止｜AI・技術一覧（100件・更新停止）`

It is retained for safety/audit purposes. **Do not invite members to it** and do not use it as a current product URL.

## Digest fulfillment contract

The LP explicitly sells a member-only Digest. Automated Digest generation is not currently relied upon for product fulfillment while the normal Daily schedule remains PAUSED.

Run217 created the first current member Digest from already-authoritative DB content only:

- Title: `会員限定Digest｜2026年9月 初回版`
- Page ID: `3d0479ff-dca9-81de-b614-fef528d2f32c`
- Gemini/model requests: **0**

Run218 moved this Digest under the real canonical member home.

Until automated Digest delivery is deliberately re-enabled and validated, the paid service must still receive at least a human/zero-model current-DB Digest for each promised monthly cycle. **Do not silently advertise Digest while delivering none.**

## Important-change semantics retained

Run217 correctly found that `今月の重要変化 = true` was 0 records at the audit time.

Do **not** change that source/state merely to make the product look active. Priority and observed change are different concepts. Run218 fixes the presentation problem instead: when the monthly flag has no rows, the primary UX may show recent large score changes from existing authoritative history without rewriting the monthly flag.

## Current onboarding checklist

Run218 is authoritative for navigation. For each paid member:

1. Confirm active note membership using the existing human verification process.
2. Invite the member to `AI Decision Intelligence｜会員ホーム` (`3c5479ff-dca9-8103-bff0-f2d5f408d35f`).
3. Do not send the internal `mlflow/mlflow` source page.
4. Do not send the legacy 100-row database.
5. Do not send the superseded Run217 home `3d0479ff-dca9-819e-9da0-c951225de6b3`.
6. Confirm the member can use the PC-first views and open the current Digest.
7. If access fails, fix Notion sharing before considering onboarding complete.

## Non-goals / safety

Run217 did not:
- call Gemini or any model API
- change Decision score or judgment
- weaken Evidence / Fact gates
- change article-generation logic
- resume Daily
- enable public note auto-release
- invent related-article URLs
- mark fake important changes
- delete the legacy DB

Run218 is the corrective navigation/UI baseline layered on these retained safety properties.
