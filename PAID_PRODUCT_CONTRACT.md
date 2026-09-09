# AI Intelligence Factory — Paid Product Contract

更新日: 2026-09-09  
状態: **Run307 current product contract — Generic Use-Decision Intelligence / Four-Source Intelligence**

この文書は有料会員商品のSource of Truthです。Evidence / Decision History / Provider budget / Notion access safety等の技術契約は変更しません。

## 1. 初期ICP

**AI・Web・業務システム等を自ら開発・導入したり、必要に応じて提案したりする、フリーランス／個人事業主／1〜3名規模の小規模事業者。**

Primary Job:
- 新しいAI・技術を見つけたとき、短時間で「このAI、使える！」と判断できる材料をそろえる。
- Evidence、比較、主なリスク、利用条件、小規模検証条件を確認する。
- 自分の開発、業務利用、必要に応じた提案のどれにも転用できる判断メモへ落とす。
- 毎日GitHub、論文、Hacker News、各社公式情報を自力で巡回しない。

**顧客提案は利用場面の一つであり、商品メッセージの主語にはしない。** 自分の開発・業務利用・提案を同じ判断基盤で扱う。

## 2. 販売する価値

旧: `AIを調べるためのNotion DB`

Run256まで: `仕事に関係するAIを理解し、使う・試す・待つ・避けるを判断するWork-First Decision Intelligence`

Run268–270: `顧客案件での技術選定・比較・説明・提案を主にするProposal-First Decision Intelligence`

現行: **新しいAI・技術について「使えるか」を、根拠付きで短時間に判断するUse-Decision Intelligence**

中心メッセージ:

> **「このAI、使える！」を、根拠付きで判断できる。**

価値の流れ:

**変化を知る → Evidenceを確認する → 使う/試す/待つ/避けるを判断する → リスクと条件を整理する → 試す・導入する次の一手へ落とす**

DB件数やニュース量は裏側の情報資産であり、購入理由として前面に出さない。販売するのは「情報量」ではなく、**使えるかどうかを判断する工程の短縮**である。

## 3. Intelligence Source Contract — Run268/269を維持

Productionで同格に巡回するSourceは次の4系統とする。商品メッセージ変更でSource architectureは変更しない。

1. **GitHub — 実装動向**  
   OSSの実装進展、更新、成熟度、保守状態、導入可能性を観測する。
2. **ArXiv — 技術の先行動向**  
   研究・技術的ブレークスルー・将来の実装候補を観測する。論文であること自体を実用性と同一視しない。
3. **HackerNews — 市場・エンジニア反応**  
   AI関連テーマに絞り、実務者・開発者の反応、論点、熱量を観測する。HN全体のTop Storiesは巡回しない。
4. **OfficialVendor — 商用利用に直結する一次情報**  
   モデル/API更新、価格、制限、context/token、SDK、互換性、deprecated/retire/migration等、利用判断へ直結する公式情報を観測する。

### OfficialVendor coverage

OfficialVendorはRound Robin上では**1 Source**として扱い、内部metadataでvendor / regionを識別する。ベンダー数をSource数へ展開しない。

欧米主要:
- OpenAI
- Anthropic
- Google Gemini

中国主要:
- Alibaba Qwen
- DeepSeek
- ByteDance Doubao / Seed
- Moonshot AI Kimi
- Zhipu AI GLM
- MiniMax
- Baidu ERNIE
- Tencent Hunyuan

中国系を補助扱いにしない。モデル性能・価格・API・OSS・商用条件の変化が利用判断に影響する場合、欧米系と同じEvidence/Decision基準で扱う。

**Product HuntはRun268からProductionのactive Sourceではない。** 過去のコード・履歴・画像資産が互換目的で残っていても、Production取得・Source ROI・Round Robinの正本には含めない。

## 4. 商品4層

1. **無料note** — 知る・面白く理解する。品質を意図的に落とさない。
2. **Decision Brief** — 今月「使えるか」の判断に影響する重要な3〜7件を先に読む。
3. **Decision Intelligence** — 必要時に全体DBで比較・根拠・リスク・履歴を確認する。
4. **Decision / Action Asset** — 利用条件、判断メモ、小規模検証条件、比較観点、次の一手へ落とす。必要に応じて提案にも転用できるが、提案テンプレート販売を本体にしない。

内部Intelligence EngineはDeep Techを含め広く保持する。内部追跡対象と会員トップ表示を同一視しない。

## 5. DBの位置づけ

- Technology / Deep Tech inventoryは削除しない。
- DBは検索・Evidence・Decision Historyエンジン。
- トップ推薦は単純な判断スコア順にしない。
- `実務判断`かつ既存品質条件を満たした中で、**自分の開発・業務利用・導入判断への関連性**をNavigation-onlyで評価する。
- `顧客` / `クライアント`という語だけで上位化しない。
- Source score / Decision / EvidenceをICP都合で改変しない。

## 6. Use-Decision表示契約 — Run307

会員向け詳細ではcanonical値を次へ翻訳して表示する。

- **いま、使える？** — canonical判断 + 判断理由を、導入・利用判断として表現する。
- **使える場面** — `向いている用途`。Evidenceがない適合を断定しない。
- **使う前に確認すること** — `主なリスク` + `向いていない用途`。
- **試す・導入する次の一手** — `次にやること`。既存の検証Actionを使い、架空の工数・ROIを追加しない。
- **Decision Update｜判断を変える必要がある？** — material changeが現在の利用判断を変える必要につながるか。
- **確認に使った公式・一次情報** — Evidence / primary URLを保持する。

根拠のないROI、売上、工数削減率を創作しない。見栄えのためにEvidenceを弱めない。

**Run307以降の最終可視本文はUse-Decisionを正本とする。**  
**Run270のProposal-First本文は歴史的互換層**として残すが、最終表示Authorityではない。Run250のWork-First本文も同様に歴史的互換層である。

値がある場合の基本順序:

`これは何？` → `いま、使える？` → `使える場面` → `なぜ今見る？` → `使う前に確認すること` → `試す・導入する次の一手` → `Decision Update｜判断を変える必要がある？` → `確認に使った公式・一次情報`

自分の開発、業務利用、提案のいずれでも使えるが、**顧客提案は利用場面の一つ**として扱う。

## 7. 日本語表現契約

主語省略を基本とする。

- `自分の仕事に使える` → `仕事に使える`
- `自分の利用条件` → `利用条件`
- `自分の作業時間` → `作業時間`

`自分だけ / 少人数 / チーム`のように主体差が意味を持つ場合は残す。

中立化そのものより**自然で意味が保たれる日本語**を優先する。`自社`の機械的一律置換は禁止。

安全な例:
- `自社案件` → `対象業務`
- `自社要件` → `利用条件`
- `自社AI` → `利用中のAI`
- `自社コード` → `独自コード`
- `自社環境` → `利用環境`

NG例:
- `自社AI` → `利用環境AI`

安全に意味を保持できない場合はcanonical表現を無理に変えない。

## 8. Decision Brief 契約

Decision Briefは「おすすめ一覧」ではない。短時間で今月の利用判断を更新する入口とする。

必須:
- 主要候補を3〜7件へ絞る。
- `使う / 試す / 待つ / 避ける` を示す。
- 自分の開発・業務利用・導入判断への意味、確認事項、次の一手を短く示す。
- **判断を変えるmaterial changeが存在する場合、少なくとも1件は具体的なDecision Updateを本文へ出す。** DB一覧へのリンクだけで代替しない。
- material changeがない月は、変化を捏造せず **「重要な判断変更なし」** と示す。

Decision Updateでは生の `82 → 91` を中心にしない。

示す順序:
1. 何が変わったか
2. その変化で利用判断をどう変えるべきか
3. なぜ今重要か
4. 次の一手

2026年9月の具体例:
- **FlowiseAI/Flowise — AVOID**
- 公式GitHubがArchived。
- 新規AIワークフロー共通基盤としては選ばず、既存構成の保守・移行判断に限定。
- 現在保守されている候補と比較する。

Decision Updateは将来 `Changed / New / Unchanged-important` を扱える。ただしPMF前に個別Watchlist・通知パーソナライズを実装しない。

## 9. Decision / Action Assetの境界

重要な候補についてのみ必要に応じて付ける。

- 利用目的・条件の確認項目
- 小規模検証条件
- 導入前チェックリスト
- 比較観点
- **判断メモ1枚**
- 最小ワークフロー例
- Evidence / リスク / 制約 / 推奨Action

必要に応じて顧客説明・提案にも転用できる。ただし、商品をプロンプト集・提案書テンプレート販売サービスにしない。Evidenceから「使えるか」の判断までを短縮するDecision Intelligenceが本体である。

## 10. note有料導線

販売導線は次を正本とする。

**無料note → 固定LP → noteメンバーシップ → 会員ホーム / Decision Brief / 判断DB**

記事末尾CTA:

> 有料サブスクでは、重要な変化を絞ったDecision Brief、根拠を確認できる意思決定DB、試す・導入する前の判断メモを提供しています。新しいAIや技術を見つけたとき、「このAI、使える！」と判断するための情報を、一次情報とEvidence付きで短時間に整理できます。

CTAリンクラベル:

**`月額1,980円の内容を見る`**

固定LPの現行copy正本は `docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md`。Public noteの編集・公開はhuman-only。

## 11. 現行Notion会員面

Home:  
`3c5479ff-dca9-8103-bff0-f2d5f408d35f`

Member DB:
- Database `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Data Source `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`

Decision Brief 2026-09:  
`3d0479ff-dca9-81de-b614-fef528d2f32c`

既存ページ名 `AI導入 判断・提案メモ`:  
`3d3479ff-dca9-8119-b0d8-c014b068fe82`

ページ名は既存実物を事実として記録する。Run307の商品価値は提案専用ではなく、判断メモを自分の開発・業務利用にも使う。

2026年9月の主要候補:
1. Dify
2. AnythingLLM
3. browser-use
4. ComfyUI
5. Cline

これは固定allowlistではない。将来は同じUse-Decision relevance契約で選ぶ。

## 12. 価格と商業検証

- 標準価格: **月額1,980円**
- 初期マイルストーン: **実有料顧客10人**
- 100人獲得はPMF入口の後。
- 価格を先に下げて商品不一致と価格不一致を混同しない。
- まず「知らない利用者が実際にカードを出すか」を検証する。
- 自分の開発・業務利用・必要に応じた提案で継続利用されることを確認後、2,980円 / 4,980円を含む価格検証を別途行う。
- noteは市場ではなく集客チャネルの一つ。
- 決済方式はProduction実装・検証済み事実のみを確定扱いする。

## 13. 非交渉事項

- Evidence / Fact / Decision品質を弱めない。
- Deep Techを削除しない。
- Source scoreをICP適合度へ置換しない。
- ICP relevanceはNavigation-only。
- OfficialVendorのvendor/regionをSource枠へ分裂させない。
- 中国系Vendorを出身地域だけで加点・減点しない。一次情報・実務影響・Evidenceで評価する。
- 新しい有料APIを追加しない。
- Gemini/model呼出しをSource取得・表示ロジックへ追加しない。
- Public note公開はhuman-only。
- Notion schemaを不用意に変更しない。
- 個別Watchlist/パーソナライズはPMF前に実装しない。
- CI greenだけを商品改定完了の証明にしない。本番Notion実物を監査する。
- 不要な `自分の` を再導入しない。
- neutralizationで不自然な複合語を作らない。
- material changeがあるのにDecision Briefを抽象論だけで終わらせない。
- UI/内部命名の美化を、販売検証・利用判断Artifact・Source品質より優先しない。

## 14. Run250–307

- Run250 — paid presentation overlay
- Run251 — legacy fixed shortlist retirement
- Run252 — production `__main__` body authority
- Run253 — Work-First correction
- Run254 — unnecessary first-person removal
- Run255 — natural/context-safe neutralization
- Run256 — concrete Decision Update + documentation reconciliation
- Run268 — Proposal-First ICP / Four-Source Intelligence / OfficialVendor East-West coverage
- Run269 — live acquisition precision / strict vendor evidence
- Run270 — Proposal-First member visible surface / static Notion surface alignment（歴史的互換層）
- **Run307 — Generic Use-Decision product / self-development + work use + optional proposal / current visible surface**

Run307はSource architecture、Evidence、Decision、Notion schemaを変更しない。表示・販売copyの変更は**ZERO Gemini/model calls**で行う。
