# AI Intelligence Factory — Paid Product Contract

更新日: 2026-09-07  
状態: **Run270 current product contract — Proposal-First Decision Intelligence / Four-Source Intelligence**

この文書は有料会員商品のSource of Truthです。Evidence / Decision History / Provider budget / Notion access safety等の技術契約は変更しません。

## 1. 初期ICP

**AI・Web・業務システム等を顧客へ提案・開発する、1〜3名規模のフリーランス／小規模開発事業者。**

Primary Job:
- 顧客から「このAI・技術を使うべきか」と聞かれたとき、短時間で根拠ある回答を作る。
- 候補技術を比較し、Evidence・主なリスク・利用条件・小規模検証条件を確認する。
- 技術選定の調査結果を、提案・見積・説明のたたき台となる判断メモへ落とす。
- 毎日GitHub・論文・HN・各社リリースノートを自力で巡回しない。

Secondary Value:
- 今後触るべき技術や、自分の学習・検証優先度を判断する。
- 技術力・市場価値の向上に使う。

**Primaryは顧客案件での技術選定・提案判断、Secondaryが自己学習。A/Bを同格にしない。**

## 2. 販売する価値

旧: `AIを調べるためのNotion DB`

Run256まで: `仕事に関係するAIを理解し、使う・試す・待つ・避けるを判断するWork-First Decision Intelligence`

現行: **顧客案件での技術選定・比較・説明・提案に必要な調査時間を短縮するProposal-First Decision Intelligence**

中心メッセージ:

> **「このAI、使える？」に、根拠付きで早く答えられる。**

価値の流れ:

**変化を知る → Evidenceを確認する → 使う/試す/待つ/避けるを判断する → リスクと条件を整理する → 判断・提案メモへ落とす**

DB件数やニュース量は裏側の情報資産であり、購入理由として前面に出さない。販売するのは「情報」そのものではなく、**技術選定と提案作成に必要な判断工程の短縮**である。

## 3. Intelligence Source Contract

Productionで同格に巡回するSourceは次の4系統とする。Sourceごとの役割を混同しない。

1. **GitHub — 実装動向**  
   OSSの実装進展、更新、成熟度、保守状態、導入可能性を観測する。
2. **ArXiv — 技術の先行動向**  
   研究・技術的ブレークスルー・将来の実装候補を観測する。論文であること自体を実用性と同一視しない。
3. **HackerNews — 市場・エンジニア反応**  
   AI関連テーマに絞り、実務者・開発者の反応、論点、熱量を観測する。HN全体のTop Storiesは巡回しない。
4. **OfficialVendor — 商用利用に直結する一次情報**  
   モデル/API更新、価格、制限、context/token、SDK、互換性、deprecated/retire/migration等、商用技術選定へ直結する公式情報を観測する。

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

中国系を補助扱いにしない。モデル性能・価格・API・OSS・商用条件の変化が顧客提案に影響する場合、欧米系と同じEvidence/Decision基準で扱う。

**Product HuntはRun268からProductionのactive Sourceではない。** 過去のコード・履歴・画像資産が互換目的で残っていても、Production取得・Source ROI・Round Robinの正本には含めない。

## 4. 商品4層

1. **無料note** — 知る・面白く理解する。品質を意図的に落とさない。
2. **Decision Brief** — 今月、顧客案件・技術選定で知っておく価値がある3〜7件を先に読む。
3. **Decision Intelligence** — 必要時に全体DBで比較・根拠・リスク・履歴を確認する。
4. **Decision / Proposal Action Asset** — 利用条件、判断・提案メモ、小規模検証条件、比較観点へ落とす。大量テンプレート市場へピボットしない。

内部Intelligence EngineはDeep Techを含め広く保持する。内部追跡対象と会員トップ表示を同一視しない。

## 5. DBの位置づけ

- Technology / Deep Tech inventoryは削除しない。
- DBは検索・Evidence・Decision Historyエンジン。
- トップ推薦は単純な判断スコア順にしない。
- `実務判断`かつ既存品質条件を満たした中で、**顧客案件での技術選定・提案関連性**をNavigation-onlyで評価する。
- `顧客` / `クライアント`という語だけで上位化しない。
- Source score / Decision / EvidenceをICP都合で改変しない。

## 6. Proposal-First表示契約

会員向け詳細ではcanonical値を次へ翻訳して表示する。

- **顧客にどう答える？** — canonical判断 + 判断理由を、顧客への技術選定回答として表現する。
- **提案できる場面** — `向いている用途`。顧客利用を裏付けるEvidenceがない場合、適合を断定しない。
- **提案前に確認すること** — `主なリスク` + `向いていない用途`。
- **提案・検証の次の一手** — `次にやること`。既存の検証Actionを使い、架空の工数・ROIを追加しない。
- **Decision Update** — material changeが技術選定・提案判断を変える必要につながるか。
- **確認に使った公式・一次情報** — Evidence / primary URLを保持する。

根拠のないROI、売上、工数削減率を創作しない。顧客向けに見栄えを良くするためにEvidenceを弱めない。

**Run270以降の最終可視本文はProposal-Firstを正本とする。** Run250のWork-First本文は歴史的互換層として残すが、最終表示Authorityではない。値がある場合の基本順序は `これは何？` → `顧客にどう答える？` → `提案できる場面` → `なぜ今見る？` → `提案前に確認すること` → `提案・検証の次の一手` → `Decision Update` → `公式・一次情報` とする。

社内利用・自己学習への転用はSecondary Valueとして残す。ただし、会員トップ・詳細本文・Decision Brief・判断メモで「顧客提案は副次利用」と表現しない。

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

Decision Briefは「おすすめ一覧」ではない。短時間で今月の判断を更新する入口とする。

必須:
- 主要候補を3〜7件へ絞る。
- `使う / 試す / 待つ / 避ける` を示す。
- 顧客案件・技術選定への意味、確認事項、次の一手を短く示す。
- **判断を変えるmaterial changeが存在する場合、少なくとも1件は具体的なDecision Updateを本文へ出す。** DB一覧へのリンクだけで代替しない。
- material changeがない月は、変化を捏造せず **「重要な判断変更なし」** と示す。

Decision Updateでは生の `82 → 91` を中心にしない。

示す順序:
1. 何が変わったか
2. その変化で技術選定・提案をどう変えるべきか
3. なぜ顧客案件で重要か
4. 次の一手

2026年9月の具体例:
- **FlowiseAI/Flowise — AVOID**
- 公式GitHubがArchived。
- 新規AIワークフロー共通基盤としては選ばず、既存構成の保守・移行判断に限定。
- 現在保守されている候補と比較する。

Decision Updateは将来 `Changed / New / Unchanged-important` を扱える。ただしPMF前に個別Watchlist・通知パーソナライズを実装しない。

## 9. Decision / Proposal Action Assetの境界

重要な候補についてのみ必要に応じて付ける。

- 顧客の利用目的・条件の確認項目
- 小規模検証条件
- 提案前チェックリスト
- 比較観点
- **判断・提案メモ1枚**
- 最小ワークフロー例
- Evidence / リスク / 制約 / 推奨Action

判断・提案メモは有料価値の中心Artifactへ格上げする。ただし、商品をプロンプト集・提案書テンプレート販売サービスにしない。Evidenceから提案判断までを短縮するDecision Intelligenceが本体である。

## 10. 現行Notion会員面

Home:
`3c5479ff-dca9-8103-bff0-f2d5f408d35f`

Member DB:
- Database `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Data Source `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`

Decision Brief 2026-09:
`3d0479ff-dca9-81de-b614-fef528d2f32c`

AI導入 判断・提案メモ:
`3d3479ff-dca9-8119-b0d8-c014b068fe82`

2026年9月の主要候補:
1. Dify
2. AnythingLLM
3. browser-use
4. ComfyUI
5. Cline

これは固定allowlistではない。将来は同じProposal-First relevance契約で選ぶ。

## 11. 価格と商業検証

- 標準価格: **月額1,980円**
- 初期マイルストーン: **実有料顧客10人**
- 100人獲得はPMF入口の後。
- 価格を先に下げて商品不一致と価格不一致を混同しない。
- まず「知らない顧客が実際にカードを出すか」を検証する。
- 顧客案件で継続利用されることを確認後、2,980円 / 4,980円を含む価格検証を別途行う。
- noteは市場ではなく集客チャネルの一つ。
- 決済方式はProduction実装・検証済み事実のみを確定扱いする。

## 12. 非交渉事項

- Evidence / Fact / Decision品質を弱めない。
- Deep Techを削除しない。
- Source scoreを顧客適合度へ置換しない。
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
- UI/内部命名の美化を、販売検証・提案Artifact・Source品質より優先しない。

## 13. Run250–270

- Run250 — paid presentation overlay
- Run251 — legacy fixed shortlist retirement
- Run252 — production `__main__` body authority
- Run253 — Work-First correction
- Run254 — unnecessary first-person removal
- Run255 — natural/context-safe neutralization
- Run256 — concrete Decision Update + documentation reconciliation
- Run268 — Proposal-First ICP / Four-Source Intelligence / OfficialVendor East-West coverage
- Run269 — live acquisition precision / strict vendor evidence
- **Run270 — Proposal-First member visible surface / static Notion surface alignment**

Run268–270のSource/商品契約変更は**新規Gemini/provider callを追加しない**。OfficialVendorは公開公式ページのbounded HTTP取得、HNはbounded Algolia queryで取得し、Run270は既存canonical値の表示変換だけを行う。
