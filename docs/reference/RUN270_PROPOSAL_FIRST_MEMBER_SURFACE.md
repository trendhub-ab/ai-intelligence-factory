# Run270 — Proposal-First Member Surface

Run270 aligns the paid member-facing UI with `PAID_PRODUCT_CONTRACT.md` after the Run268 business pivot.

## Authority boundary

- Run268 / `PAID_PRODUCT_CONTRACT.md` remain the business and paid-product authority.
- Run250 remains a historical Work-First compatibility layer and is not deleted.
- Run270 installs after Run250 and is the current member presentation authority.
- Evidence, Decision Score, canonical status, source data, Deep Tech inventory, and Notion schema are unchanged.
- ZERO Gemini/model calls.

## Primary ICP

AI・Web・業務システム等を顧客へ提案・開発する、1〜3名規模のフリーランス／小規模開発事業者。

Primary Job:

> 顧客から「このAI / 技術を使うべきか？」と聞かれたとき、調査・比較・リスク確認・提案作成を短時間で終わらせる。

Internal work use and skill growth remain secondary benefits, not the product center.

## Member DB detail-page contract

The generated member detail body uses only already-authoritative fields and presents them in this order when available:

1. `これは何？`
2. `顧客にどう答える？`
3. `提案できる場面`
4. `なぜ今見る？`
5. `提案前に確認すること`
6. `提案・検証の次の一手`
7. `Decision Update｜提案を変える必要がある？`
8. `確認に使った公式・一次情報`

The navigation ranker remains Run250's proven navigation-only ranker for Run270. Run270 does not change source scores or factual quality scores.

## Static Notion surface contract

These pages are static member surfaces rather than generated Member Presentation DB item bodies. Their IDs are intentionally documented here so the business contract and the live product can be audited together.

### Member Home

Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`

Primary opening:

> 顧客に「このAI・技術を使うべきか？」と聞かれたとき、根拠付きの導入判断と提案下書きまで短時間で作るための会員ページです。
>
> 技術を全部追う必要はありません。重要な変化、使う・試す・待つ・避ける判断、提案前の確認点をここから辿れます。

The Home must not describe client proposal use as merely a secondary reuse case.

### Monthly Decision Brief

Current September page ID: `3d0479ff-dca9-81de-b614-fef528d2f32c`

Primary framing:

> 今月は、顧客から「このAI・技術を使うべきか？」と聞かれたときに確認すべき重要項目だけを絞っています。

The Brief should answer: what changed, whether the proposal judgment should change, what to verify before proposing, and what action comes next.

### AI導入 判断・提案メモ

Current page ID: `3d3479ff-dca9-8119-b0d8-c014b068fe82`

Target title:

`AI導入 判断・提案メモ｜使う・試す・待つ・避ける`

Target introduction:

> 顧客案件でAI・技術を提案する前に、判断根拠と検証条件を1枚にまとめるメモです。社内利用やADRにも転用しやすい判断フォーマットです。

Nine-field memo:

1. 顧客課題 / 提案シーン
2. 候補AI / 技術
3. 今回の判断
4. 採用 / 試用理由
5. 向かない条件
6. 主なリスク
7. 最小検証
8. 成功条件
9. 次の判断 / 提案更新日

Do not claim that this is automatically a complete ADR or a complete client proposal. It is a decision/proposal memo that can be reused in those workflows.

## Live Notion audit — 2026-09-07 JST

After the static-surface edits, all three live Notion pages were re-fetched directly and audited before merge.

### Member Home audit

Observed page: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`

PASS:

- opening is Proposal-First: `顧客に「このAI・技術を使うべきか？」と聞かれたとき、根拠付きで早く答えられる。`
- the primary purpose is customer-project technology selection, comparison, explanation, and proposal;
- navigation is framed as `提案シーンから見る`;
- Decision Update asks whether customer proposal / technology-selection judgment should change;
- the judgment memo link resolves to the renamed `AI導入 判断・提案メモ｜使う・試す・待つ・避ける` page;
- existing Decision Brief link, Member DB views, Deep Tech link, five recommended technologies, and child-page structure remain present.

### September Decision Brief audit

Observed page: `3d0479ff-dca9-81de-b614-fef528d2f32c`

PASS:

- opening is Proposal-First and explicitly addresses the customer question `このAI・技術を使うべきか？`;
- the five existing candidates remain Dify / AnythingLLM / browser-use / ComfyUI / Cline;
- existing decisions and scores remain Dify ADOPT 91, AnythingLLM TEST 82, browser-use TEST 81, ComfyUI TEST 86, Cline TEST 84;
- each item uses `提案できる場面`, `顧客案件への意味`, `提案前に確認すること`, and `提案・検証の次の一手`;
- existing DB links and official GitHub links remain present;
- Flowise remains the concrete material-change example and is still framed as new-adoption avoidance based on the archived official GitHub state.

### AI導入 判断・提案メモ audit

Observed page: `3d3479ff-dca9-8119-b0d8-c014b068fe82`

PASS:

- title is `AI導入 判断・提案メモ｜使う・試す・待つ・避ける`;
- opening makes customer-project proposal judgment the primary use;
- ADOPT / TEST / WATCH / AVOID remain unchanged;
- the nine-field memo is present with the Run270 field names;
- `最小検証` is customer-project-like and bounded rather than full rollout;
- internal use and ADR reuse are explicitly secondary/reuse cases, not the product center;
- no Notion schema change was introduced by this static-page edit.

### Audit conclusion

`LIVE_NOTION_STATIC_SURFACES=PASS`

The static Notion product surface now matches the Run268 paid-product strategy and the Run270 member-visible Proposal-First authority without changing canonical Evidence, Decision Score/status, source data, Deep Tech inventory, or Member Presentation DB schema.

## Regression contract

Run270 must fail closed if:

- the generated member body returns to Work-First headings as the final visible authority;
- Run270 installs before Run250;
- client proposal becomes secondary in the Run270 contract;
- the member sync workflow stops testing Run270;
- source scores, decision status, Evidence, or Notion schema are redefined by Run270;
- Gemini/model calls are introduced into this presentation layer.

## Operational note

Daily remains PAUSED and public note publication remains human-only. Run270 is a paid-member presentation alignment, not a source, scoring, article-generation, or schema migration change.
