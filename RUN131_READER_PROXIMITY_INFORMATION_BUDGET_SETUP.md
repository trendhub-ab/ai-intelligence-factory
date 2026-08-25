# Run131 Reader Proximity + Information Budget

## 目的
Run129/130の実稿で、日常語や身近な題材が存在しても「詳しい友人が隣で話している」距離感が発現しないケースを確認した。また、専門語ごとに比喩や説明を足すと2,000〜3,200字の本文予算を圧迫し、Evidence・制約・Decisionを薄くするか、説明面積増加によってSource Boundary違反を増やす反証が成立する。

Run131は、親近感を「固定口癖」ではなく読者との機能的な接点として最低限成立させ、同時に説明を足し算しないEditorial Information Budgetを導入する。

## 生成ロジック
- 1記事に原則1〜3箇所、読者の実体験を想起させる問い、難しい名前への一言、身近な場面への接続等の「読者との距離が近くなる一文」を自然に成立させる。
- 「ですよね」「なんですよ」等は必須語にしない。固定句や同じ語尾の反復を避ける。
- 親近感の一文は新規段落として足さず、既存の硬い説明・接続文を置き換える。
- 読者が持ち帰る専門概念を内部で2〜4個に絞り、Decision理解に必須の概念だけを丁寧に翻訳する。
- その他の内部実装・規格名・略語は、Evidence/制約を失わない範囲で圧縮するか、本文理解に不要なら書かない。
- 文字数を確保するためにEvidence、数値、制約、比較、反証、Decisionを削らない。削減優先は重複説明、不要な内部実装、汎用前置き、同義反復。
- 日常例・会話文からEvidenceにない固有名詞、数値、市場評価、利用実績を作らない。

## 0-API監査
Reader Experience Auditに以下を追加/精密化する。
- Reader Proximity
- Reader Proximity Moment Count
- Information Budget
- Conversational Warmthの判定精密化

Run129では「スマホ」等の日常語があるだけでもWarmth扱いになり得た。Run131では、実際の問いかけ・読者への語り・難しい概念を近づける一言がなければ `REVIEW_MISSING` とする。

これらはsoft-only。Warmth不足だけでGemini Quality Retryを追加せず、Rejected率/API消費を増やさない。

## 非変更領域
- Fact / Evidence / Publication / Decision Hard Gate
- Quality Retry budget
- Gemini API call site
- Notion schema
- Fresh Article Regression fixed/fresh互換
