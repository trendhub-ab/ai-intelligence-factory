# Run345 — Reader Concept Hierarchy

## 結論

Run41の実Production原稿3本を0-APIで反証した結果、Human Appeal / 非エンジニア可読性の主因は「Reader向け指示不足」ではなかった。既存のcanonical promptには既に、Reader Proximity、普通の言葉への翻訳、専門概念を原則2〜3個へ絞ること、長い説明の削除・統合が存在する。それでも3本が共通して専門語・方式名・ベンチマーク名を過剰に本文へ残した。

したがってRun345ではルールを増やすのではなく、`run208_reader_value_repair.py` の追加契約を再編し、競合時に何を優先し何を捨てるかを一つの実行階層として固定する。

## 実Productionでの反証

### DeepSeek v4.1 Flash

Run344後もPublication ReadinessはPASSしたがHuman AppealはWEAK。最終稿ではReader Proximityが0、会話マーカー0、Jargon Translationが弱く、V4 / SSD / KVなどの未説明語が残った。冒頭からAPI、Causal Encoder-Decoder、Sparse MoE、KV/HBM/SSD等へ進み、読者がDecisionを自分事として保持する前に技術概念が増えた。

### DeepSeek-v4.1-Exp

Reader ProximityとPlain-Language Bridgeが存在してもHuman AppealはWEAKだった。CED、CSA2、FP4、KV、Reasoning Effort、Jinja等が同じ表面へ並び、Information BudgetもREVIEW。これは「会話的な一文を足せば解決する」という仮説を否定する。

### Layer-Selective Unlearning

冒頭の非エンジニアアクセスとPlain-Language BridgeはGOODでも、PTQ / TOFU / MUSE / GA / NPO / KLD / SURE / LUNAR等が後半で増え、Implementation Detail LoadとReader Temperature RhythmがREVIEWになった。これは「冒頭600字だけ直せば十分」という仮説も否定する。

## Run345の変更

Reader向けの実行優先順位を次に固定する。

1. Decision理解
2. 重要な制約・対象範囲・例外・未検証条件の保持
3. Decisionを支えるEvidence
4. なぜそうなるかを理解するための中核メカニズム1つ
5. 実装名・略語・ベンチマーク名

下位の情報が上位の理解を阻害する場合は、下位を削除・カテゴリ化・圧縮する。一次情報に名称が存在すること自体は、無料ARTICLE本文へ転記する理由にしない。

冒頭約600文字では中核メカニズムを1つまでにし、方法名・略語・ベンチマーク・内部部品が3個以上の列挙になりそうならEvidence inventoryとして扱う。個々の名前の違いがDecisionまたは重要な制約を変える場合だけ例外とする。

Reader Repairでも「後段へ移動」だけで済ませず、Decisionに不要な技術名はまず削除または意味カテゴリへ圧縮する。Human Appealのための会話句・雑談・比喩の追加は禁止し、読者への近さは自分との関係、判断の速さ、具体Actionで作る。

## 変更しないもの

- Fact Gate
- Evidence Gate
- Publication Gate
- Reader Gateの閾値
- Deep Dive model routing
- Gemini request budget
- retry回数
- Notion write policy
- Note Ready policy
- runtime layer数

Run345は新しいprovider call、provider loop、budgetを追加しない。既存の`run208_reader_value_repair.py`へ統合する。

## 成功判定

次回の通常Productionで、単にReader Proximityの語句が増えたかではなく、次を確認する。

- Human Appeal / Non-Engineer Core Clarityが改善すること
- Jargon TranslationとInformation Budgetが改善すること
- Decision / Evidence / limitation fidelityが維持されること
- 技術名の列挙が減ってもFact/Evidence Gateを通ること
- `Deep Dive → Ready` Publish Yieldが改善すること

単一記事・単一スコアだけで成功とは判定しない。
