# AI Intelligence Factory — Canonical Article Contract V1

Date: 2026-09-19  
Status: Design specification — implementation not yet started  
Repository: `trendhub-ab/ai-intelligence-factory`

## 1. Purpose

AIIFの無料note記事について、Writer、Editorial Blueprint、Reader Gate、Human Appeal、Publication Gate、Quality Retry、Reader Repairが別々の「良い記事像」を持つ状態を解消する。

本Contractは、記事生成・修復・評価の共通正本である。目標はGate通過率そのものではなく、次の読者体験を安定して作ることにある。

> AI・ITに詳しい人から面白い話を聞いていたら、専門知識がなくても核心を理解でき、自分ならどう判断するかまで決められた。専門家が読んでも事実・条件・Evidenceは崩れていない。

本Contractは品質Gateを緩和しない。Provider呼び出し回数を増やさない。新しいAI Providerや新しい記事生成callも追加しない。

## 2. Canonical priority

記事品質の優先順位は次で固定する。

1. Fact / Evidence integrity
2. Decision fidelity
3. Reader comprehension
4. Article-specific discovery / interest
5. Surface polish

下位品質のために上位品質を壊してはならない。

- 読みやすさのためにEvidence、重要数値、条件、反証、対象範囲を落とさない。
- Evidenceを全部見せるために、Decisionに不要な名称・実装詳細・重複説明を残さない。
- Human Appealのために、架空の経験・感情・因果・会話・多数派認識を作らない。
- Publication安全のために、根拠のある面白さや明確なDecisionまで無意味に弱めない。

## 3. Canonical article dimensions

全レイヤーは次の7要素を同じ意味で扱う。

### 3.1 Reader Question

この記事を読むことで、最優先読者のどの疑問・迷い・選択が解消するか。

Reader Questionは記事の情報選択基準であり、固定見出しではない。

### 3.2 Why Now

なぜ今読む価値があるか。

公開、更新、仕様変更、採用、問題発見など、取得済みEvidenceで確認できる理由だけを使う。確認できない「最新」「急速に普及」「業界が注目」は作らない。

### 3.3 Central Conclusion

記事全体で最も重要な読者向け結論。

発表要約ではなく、既存Decisionと整合する中心判断とする。タイトル、導入、本文、結論の緊急度・推奨距離はこの結論と矛盾してはならない。

### 3.4 Discovery

読者が「そういうことだったのか」と理解できる記事固有の核心。

単なるニュース要約、機能列挙、仕様書の言い換えをDiscoveryとして扱わない。Evidence内の意外な差分、因果、制約、比較、判断の分かれ目から選ぶ。

### 3.5 Capability Boundary

「できる」「できない」「まだ分からない」を分離する。

- 「できる」はEvidenceが支える範囲だけ。
- 「できない」は禁止・非対応・制約がEvidenceで明示される場合だけ。
- Evidenceがないだけの場合は「未確認」「まだ分からない」とする。

### 3.6 Reader Decision

既存Decisionを、読者の次Actionが分かる自然な日本語へ翻訳する。

内部管理コード NOW / TRY / WATCH / WAIT / AVOID を公開本文に出さない。試す、比較する、待つ、見送る、条件付きで導入する等の行動距離は既存Decision / Score / Actionと一致させる。

### 3.7 Evidence Integrity

Central Conclusion、Capability Boundary、Reader Decisionを支える一次情報、重要数値、条件、対象範囲、反証を保持する。

Evidenceの深さを、技術名・API名・規格名・ベンチマーク名の多さで表現しない。

## 4. Writer contract

Writerの中心原則は次とする。

> 記事を全部説明するな。読者が正しく判断するために必要な情報を選び、最も自然な順番で渡す。

### 4.1 Information selection

本文に残す情報は、少なくとも次のいずれかに必要でなければならない。

- Reader Questionへの回答
- Central Conclusionの理解
- Capability Boundaryの理解
- Reader Decisionの理解
- 重要なEvidence / 反証 / 条件

これらに不要な周辺仕様、内部実装名、コマンド名、規格番号、重複説明、名称紹介は削除または意味カテゴリへ圧縮する。

### 4.2 Terminology

専門語の固定個数制限は設けない。

必要な専門語は残す。ただし初出では、可能な限り「普通の言葉で何をするものか」を先に示し、その後で正式名称を出す。

専門語を別の未説明専門語で説明しない。

### 4.3 Structure

Canonical Article Contractの7要素を固定見出しや固定順序にしない。

記事ごとに最も自然な流れを選ぶ。Reader-first summaryの「何が出た？／なぜ重要？／結論は？」を本文テンプレートにしない。

### 4.4 Human Appeal

Human Appealは会話句の個数ではなく、次で作る。

- 記事固有の意外性
- 読者との関係
- 比較
- 因果
- 判断の分かれ目
- 具体的な意味

「ですよね」「実は」「つまり」「ここが面白いところです」等は任意であり、存在自体を品質条件にしない。

Security / Risk / Governance等では、落ち着いた文章でも核心・制約・Decisionまで自然に理解できればHumanである。

### 4.5 Tone

基本はです・ます調。

教師の講義や監査報告書ではなく、「AI・ITに詳しい人が、面白いところを順番に見せる」距離感を目標とする。

AI的な接続詞・定型句・同型見出しを繰り返さない。

## 5. Layer responsibilities

各レイヤーの責務を重複させない。

### 5.1 Evidence / Fact

質問: 正しいか。

責務:
- 数値、単位、主体、対象範囲、条件、因果、固有名詞
- Evidence sufficiency
- Unsupported claim
- Conditionality loss

ここはfail-closedを維持する。

### 5.2 Publication

質問: 公に出して安全か。

責務:
- headline / intro overclaim
- unsupported conclusion
- Decision / Score / Actionとの公開上の矛盾
- source sufficiency
- late public-surface integrity

Readerの文章趣味をPublicationへ重複登録しない。

### 5.3 Reader

質問: 非専門家でも核心と判断まで辿れるか。

責務:
- 専門語連鎖
- plain-language bridge
- non-engineer core clarity
- unnecessary implementation inventory
- dense report cluster
- narrative progression
- final-summary comprehension

### 5.4 Human Appeal

質問: 読み続ける理由と人間の編集視点があるか。

責務:
- article-specific angle
- decision voice
- generic monitoring collapse
- over-hedging
- AI-style composite
- cross-article fingerprint
- fabricated personal experience

Reader comprehensionと同じ欠陥を別名で二重にRetry対象へしない。

## 6. Retry contract

Retryは独立した記事思想を持たない。

初稿と同じCanonical Article Contractを使い、「違反したdimensionだけを修復する」。

### 6.1 Base quality retry

Fact / Evidence / Publication / Decision consistencyの具体的原因だけを修復する。

新しいReader演出を追加しない。

### 6.2 Reader repair

Fact / Evidence / Decisionを固定し、Reader dimensionだけを修復する。

優先順位:

1. Reader Decision理解
2. 重要制約
3. Evidence
4. 判断に必要な中核メカニズム
5. 実装名・略語・名称inventory

Reader Repairは新しいFact、因果、数値、経験、保証、競合情報を追加しない。

### 6.3 Retry budget

既存のbounded retry ownershipを維持する。

Canonical Contract導入を理由に追加Provider call、retry loop、daily budget増加を行わない。

長期目標は初稿品質を上げ、Retry率を下げることである。

## 7. Gate interaction rules

1つの根本欠陥を複数Gateが別Reasonとして重複登録し、複数Retryを誘発しない。

例:

- 専門語密度によって核心理解ができない場合、Readerがowner。
- Evidenceにない技術断定はFactがowner。
- Decision Scoreに対して本文だけ過度に緊急ならPublication / Decision consistencyがowner。
- 架空の使用経験はHuman AppealだがHARD扱いを維持する。

Reason codeは「どのContract dimensionに違反したか」と「どのGateがownerか」を区別できる構造を目標とする。

## 8. Final public surface

タイトル、30秒要約、本文、CTA等の組み立て後もContractを壊してはならない。

Final Surfaceは本文全体のReader Gateを重複実行する場所ではない。

責務はlate-stageで生じる以下の狭い問題に限定する。

- タイトル括弧崩れ
- 要約断片
- 要約だけで発生した専門語密集
- assemblyが作った日本語破損
- presentation-only defect

## 9. Non-goals

V1では次を行わない。

- Gate閾値を下げる
- Fact / Evidence安全基準を緩める
- Reader Gateを削除する
- Human Appealを単なるSOFT warningへ降格する
- 新しいProviderを追加する
- Gemini call数を増やす
- 新しいBlueprint生成用AI callを追加する
- BlueprintをJSON中間成果物としてpersistする
- note公開を自動化する
- Scheduled Dailyを再開する
- 固定記事テンプレートを導入する
- 「専門語3個まで」等の機械的個数制限を復活させる

## 10. Implementation direction

既存Run226のEditorial BlueprintをCanonical Article Contractの中心へ昇格する。

想定する実装方針:

1. Canonical Contractを独立した単一モジュール／正本定義へ移す。
2. Run226 / Run228 / Run208 / Run248の重複prompt契約を正本参照へ置換する。
3. Writer初稿に必要な短い実行指示だけを組み立てる。
4. RetryはCanonical dimension + actual gate reasonsから局所指示を生成する。
5. Gate実装は原則維持し、ownership重複のみテストで可視化する。
6. Final Surfaceはlate-stage defectのみを担当する現方針を維持する。
7. Publication policy fingerprintに影響する変更は既存provenance contractへ従う。

既存正常Production挙動を守るため、一括置換ではなくTDDで段階移行する。

## 11. Testing requirements

実装時は最低限、以下をZero-APIで固定する。

### 11.1 Contract assembly

- Fresh WriterがCanonical Contractを1回だけ受け取る。
- Reader / rhythm / quality instructionが同義反復で複数回入らない。
- legacy fixed-count quotaが再混入しない。
- required qualifier / Evidence / Decision safety instructionが消えない。

### 11.2 Article specimens

少なくとも以下を回帰fixture化する。

- RubyGems: Reader density / jargon repair
- ZCode: score narrative + dense report + non-engineer access
- Claude Code / AGENTS.md: Publication PASS後のReader weakness
- Inference-Engine Fingerprinting: conditionality repair後のReader regression

各fixtureについて、Contractが期待するowner dimensionを検証する。

### 11.3 Gate ownership

- Fact欠陥をReaderがownerにしない。
- Reader-only欠陥をPublicationへ重複登録しない。
- final surfaceがbody-wide Reader診断を再生成しない。
- fabricated experienceはHARDのまま。
- unknown safety reasonはfail-closedのまま。

### 11.4 Retry

- Base retryは最大1回。
- Reader-only repairは既存bounded owner contract内。
- Fresh candidate境界でretry stateが漏れない。
- Retryによって新しいFact / Evidenceが追加されない。
- Provider request budgetを増やさない。

### 11.5 Full regression

- Targeted contract tests
- Existing Reader / Publication / Fact / Retry suites
- Repository-wide deterministic pytest
- Synthetic Regression Suite
- Integration Reconciliation CI
- Repository-wide Falsification Guard
- Notion Access Policy Guard

実Provider E2Eは決定論テスト完了・main統合後に、ユーザーの明示許可を得て別工程で実施する。

## 12. Success criteria

V1実装成功はReady率だけで判断しない。

最低条件:

- Gate基準を緩めていない。
- Provider call budgetを増やしていない。
- Promptの重複・矛盾が減っている。
- Writer / Retry / Gateが同一品質定義を参照している。
- Retryによる別品質欠陥の再発が減る構造になっている。
- 既存決定論回帰がPASSする。

実記事での品質成功は、その後のbounded live validationで次を確認する。

- 初稿でFact PASS
- Publication PASS
- Reader PASS
- Human Appeal ACCEPTABLE以上
- Ready到達
- note非公開下書きまでのE2E

このlive resultを得るまでは「記事品質改善がProductionで実証された」とは扱わない。

## 13. Migration principle

この変更は「新しい品質思想の追加」ではない。

既存Run226 / Run228 / Run208 / Run248等に既に存在する良い原則を、1つの正本へ統合する作業である。

よって、実装時の原則は次とする。

- 新規ルールを足す前に重複ルールを減らす。
- Gateを変える前にPromptの整合性を直す。
- Retryを増やす前に初稿を改善する。
- 閾値を変える前にfalse positive / ownership conflictを証明する。
- Production実記事で再現していない仮説だけで基準を変更しない。
