# AI Intelligence Factory
# Notion Decision Intelligence DB 改築・実装指示書
## 事業戦略整合性 再検証版
作成日: 2026-08-21

---

## 0. この指示書の目的

AI Intelligence Factory の現行 Notion DB を、単なる「記事・候補の保存先」から、
**有料会員が継続利用する「AI技術の意思決定データベース（Decision Intelligence DB）」へ改築する。**

この改築は、現在の事業戦略と必ず整合させること。

### 現在の事業戦略
- **無料note**：集客・認知・信頼形成のための無料メディア
- **有料Subscription**：Notion DB ＋ 月次サマリーを主商品とする
- 記事単体は原則無料。有料記事販売を主収益源にしない
- 有料価値は「記事を読むこと」ではなく、**大量の一次情報から重要技術を選別し、比較・採用判断・リスク確認・評価変化を短時間で把握できること**
- 海外展開は現時点では優先しない。まず日本市場で有料需要を検証する
- 独自SaaS、複雑なダッシュボード、大規模UI開発は現段階では行わない
- 既存の AI Intelligence Factory Pipeline は捨てず、可能な限り再利用する

---

# 1. 戦略整合性の再検証結果

## 結論

**方向性は正しい。ただし、現在案のままではまだ「記事倉庫の高機能版」に留まる危険がある。**

以下の5点を必須修正とする。

### 必須修正1：Pipeline管理Statusと採用判断Statusを分離する

既存の `Status`、`Content Status`、`Article Status` は、Pipeline内部の状態管理に使用しているため、意味を変更・上書きしてはならない。

新規に以下を追加する。

**Adoption Status**
- WATCH
- TEST
- ADOPT
- AVOID

既存の `Status=Stocked` 等はそのまま維持すること。

---

### 必須修正2：Decision Score の意味を実コードで監査する

現行の `Decision Score` が、

- 技術の採用価値・実装価値を評価するスコアなのか
- 記事化価値・ニュース価値・重要度を評価するスコアなのか

を、**実装コード・Prompt・保存ロジックを確認して判定すること。**

#### 判断ルール

A. 現行 Decision Score が「技術採用判断」を十分表している場合  
→ 名称を維持し、Decision Intelligence DB の主要スコアとして利用可。

B. 現行 Decision Score が「記事価値・ニュース価値・注目度」を含む場合  
→ 既存 Decision Score を壊さず維持し、別途 **Adoption Score** または **Technology Decision Score** を新設する。

**既存スコアを意味だけ変更して流用してはならない。**  
過去データとの互換性と評価履歴が壊れるためである。

---

### 必須修正3：Final>=60だけ保存する現行条件を、商品DBにはそのまま適用しない

現行Pipelineでは原則として `Final >= 60` の項目だけ Notion Stock に保存している。

しかし Decision Intelligence 商品では、

- AVOIDすべき重要技術
- 一度高評価だったが急落した技術
- WATCH中で今後変化を追うべき技術
- 市場では話題だがProduction Readyではない技術

にも価値がある。

したがって、

**「記事化・Stock保存の閾値」と「技術追跡対象になる条件」を分離すること。**

新たに概念として以下を設ける。

### Tracking Eligibility
技術を継続監視対象へ入れるかどうかの判定。

Tracking Eligibility は単純な Final Score だけで決めない。

候補例：
- 市場インパクトが大きい
- GitHub / HN / arXiv / Product Hunt / Official Docs など複数Signalがある
- Deep DiveまたはEvidence検証の対象になった
- 今後の採用判断変化を追う価値がある
- AVOID判断そのものが利用者に有益

実装前に、現行Score体系との整合を確認して最小限のルールを設計すること。

---

### 必須修正4：履歴DBを独立させる

`Previous Score` と `Score Change` だけでは履歴資産にならない。

例：

- 6月：55 / WATCH
- 7月：63 / WATCH
- 8月：72 / TEST
- 9月：81 / ADOPT

という変化を保持するには、現在値DBだけでは不足する。

したがって、Notionを最低でも以下の2DB構成にする。

1. **Technology Intelligence DB**
2. **Decision History DB**

---

### 必須修正5：「再評価ループ」を実装要件に含める

Decision Intelligence の商品価値は、初回評価ではなく **評価がどう変わったか** にある。

新規候補だけ評価し続ける構造では商品にならない。

少なくとも以下の再評価トリガーを検討する。

- 新しい一次情報を検出したとき
- GitHub / Docs / Paper / Release 等に重要更新があったとき
- 前回評価から一定期間経過したとき
- 月次サマリー作成前
- WATCH / TEST 中の重要技術

ただしAPIコストを抑えるため、全件毎日再評価はしない。

**Change-driven + Periodic Review** を基本とする。

---

# 2. 正式な商品構造

## A. 無料note

役割：
- 集客
- SEO
- 認知
- 信頼形成
- 有料DBへの導線

無料noteは今後も原則無料とする。

記事品質Pipelineは現在の基準を維持する。

**DB改築のために記事品質ロジックを破壊・簡略化してはならない。**

---

## B. Technology Intelligence DB

有料会員が日常的に閲覧する商品本体。

原則として、

**1 Technology / Project = 1 Record**

とする。

記事単位・URL単位でレコードを増殖させない。

### 推奨プロパティ

#### 商品表示用
- Technology / Project Name
- Primary URL
- Source
- Category
- Decision Score または新設 Adoption Score
- Adoption Status
- Evidence Confidence
- Production Readiness
- Main Risk
- Best For
- Avoid For
- Short Rationale
- First Seen
- Last Reviewed
- Previous Score
- Score Change
- Last Change At
- Related Article
- Primary Evidence URLs

#### 管理用
- Canonical Entity ID
- Tracking Status
- Tracking Eligibility
- Last Evidence Update
- Next Review
- Pipeline Status（既存値を維持）
- Content Status（既存値を維持）
- Article Status（既存値を維持）
- Subscription Visibility（既存運用との整合を取る）
- Screening Score
- Reason
- Source Summary
- Published At
- Analyzed At

### 注意

「有料会員に見せる列」と「内部運用列」は分けること。

NotionのViewを使い、Subscriber View には内部Pipeline管理情報を必要以上に見せない。

---

# 3. Decision History DB

技術評価の時系列履歴を蓄積するDB。

### 必須プロパティ
- Technology（Technology Intelligence DBへのRelation）
- Reviewed At
- Decision Score / Adoption Score
- Adoption Status
- Production Readiness
- Evidence Confidence
- Main Risk
- Change Reason
- Evidence Added
- Previous Score
- Score Delta
- Previous Adoption Status
- Status Changed（Yes / No）

### 保存方針

履歴を無制限にノイズ化しない。

以下のいずれかで履歴を保存する。

- 評価値が変わった
- Adoption Status が変わった
- 重要Evidenceが追加された
- Main Risk が変わった
- 定期Snapshot（月次等）

「何も変わっていないのに毎日1行追加」は避ける。

---

# 4. Entity Identity / 重複防止

Decision Intelligence DB では、同じ技術について複数記事・複数URLが存在しても1つのTechnologyとして管理する必要がある。

既存のURL完全一致だけでは不十分。

### Canonical Entity ID の候補
- GitHub：owner/repo
- arXiv：paper ID / DOI
- Product：公式ドメインまたは公式Product ID
- Framework / Model：公式プロジェクト名＋公式URL
- HN：HN URLではなく、元となるTechnology / Projectへ紐付ける

既存の重複除去ロジックを壊さず、Technology単位のUpsertキーを追加する方向で設計すること。

---

# 5. 月次サマリーの正式な役割

月次サマリーは「今月の記事一覧」にしてはならない。

商品価値は **What Changed?** に置く。

### 月次サマリー主要セクション

1. 今月 ADOPT になった技術
2. WATCH → TEST に上がった技術
3. TEST → ADOPT に上がった技術
4. 評価が大幅上昇した技術
5. 評価が大幅下落した技術
6. AVOIDに変更された技術
7. 新規WATCH入りした技術
8. Production Readiness が変化した技術
9. 新しい重要Evidenceが追加された技術
10. 来月優先監視すべきTechnology
11. 今月の総括
12. 実務Action / Recommended Next Steps

月次サマリーは、できる限りDecision History DBから自動生成できる構造にする。

---

# 6. Adoption Status の定義

名称だけでは運用がぶれるため、最低限の定義を固定する。

## WATCH
重要性はあるが、現時点では本番採用・本格検証を推奨するだけのEvidenceまたは成熟度が不足。

## TEST
PoC、Sandbox、限定環境などで試す価値がある。  
ただしProduction投入には追加検証が必要。

## ADOPT
対象ユースケースにおいて、Evidence・成熟度・制約を踏まえ、実務導入を積極的に検討できる。

## AVOID
現時点では採用を推奨しない。  
重大な制約、成熟度不足、Security/Reliability上の問題、Evidence不足、代替優位など、明確な理由を必須とする。

### 重要
Status は人気ランキングではない。

GitHub Star数が多いからADOPT、新しいからWATCH、低スコアだからAVOID、という単純判定は禁止。

必ずEvidenceと対象ユースケースに基づく。

---

# 7. Production Readiness

最低限、以下の3段階で運用することを推奨する。

- LOW
- MEDIUM
- HIGH

必要なら将来、EXPERIMENTAL / EARLY / PRODUCTION READY などに拡張できるが、初期MVPでは分類を増やしすぎない。

---

# 8. Evidence Confidence

候補：
- LOW
- MEDIUM
- HIGH

判定材料：
- Primary Source解決状況
- Official Docs
- GitHub実装
- Paper
- Release Notes
- Benchmark条件
- Limitations
- 重要主張の裏付け
- 複数一次情報間の整合

既存 Evidence-to-Decision Sufficiency と矛盾しない形で設計する。

---

# 9. Main Risk / Best For / Avoid For

この3項目は商品価値が高いので必須。

### Main Risk
利用者が導入前に知るべき最大リスクを1〜2文で明示。

### Best For
どのユースケースなら価値を出しやすいか。

### Avoid For
どのユースケースでは使うべきでないか。

単なるAI生成一般論を禁止する。

必ず一次情報・Evidence・技術特性に基づく。

---

# 10. 既存Pipelineとの接続方針

既存Pipelineは原則維持する。

現行の概念：
- GitHub
- Hacker News
- arXiv
- Product Hunt
- Pre-Filter
- Batch Screening
- Global Calibration
- Evidence Sufficiency / Evidence-to-Decision Sufficiency
- Deep Dive
- Quality Gates
- Notion Persistence

を捨てない。

### 新しい流れのイメージ

Sources  
↓  
Pre-Filter  
↓  
Screening  
↓  
Calibration  
↓  
Tracking Eligibility 判定  
↓  
Evidence Verification  
↓  
Deep Dive / Decision Assessment  
↓  
Technology Identity 解決  
↓  
Technology Intelligence DB Upsert  
↓  
必要な場合のみ Decision History DB Append  
↓  
無料note記事生成・公開フロー  
↓  
月次 What Changed? Summary

記事公開とDB保存を完全に同一条件へ縛らないこと。

---

# 11. 現行Notionプロパティとの互換性

現在確認されている既存項目例：

- Name
- URL
- Source
- Engagement
- Decision Score
- Status
- Content Status
- Article Status
- Subscription Visibility
- Screening Score
- Reason
- Source Summary
- Published At
- Analyzed At

### 原則
既存列は勝手に削除・名称変更しない。

まず実コードで参照箇所を確認する。

その上で各項目を以下へ分類する。

- KEEP：そのまま維持
- RENAME：安全なMigrationが可能な場合のみ
- ADD：新規追加
- DEPRECATE：コード参照を除去後、非表示化
- INTERNAL ONLY：Subscriber Viewから隠す

---

# 12. 実装前に必ず行うコード監査

この指示書だけを見て推測実装してはならない。

リポジトリが渡された場合は、Notion DBに関係するファイルだけでなく、以下のロジックを横断確認すること。

- Candidate model / data schema
- Screening score
- Calibration score
- Decision Score
- Evidence assessment
- Deep Dive structured output
- Quality Gates
- Notion persistence
- Duplicate prevention
- Upgrade / Upsert logic
- Pending Retry
- Monthly Digest / summary generation
- Tests
- GitHub Actions / daily workflow
- Environment variables

### 特に確認すること
1. Decision Score の実際の意味
2. `Status` の参照箇所
3. Final>=60 のNotion保存条件
4. Notion pageのUpsert Key
5. 同一Technology再検出時の挙動
6. 既存レコード更新時に履歴が消えないか
7. Product Hunt URL resolution 等の既存Evidence補助処理
8. 4 Quality GatesのロジックがDB改築で壊れないか

---

# 13. 実装ポリシー

## 絶対条件

- 既存記事品質ロジックを壊さない
- 既存Notion Persistenceを無断で全面書き換えしない
- 既存Statusの意味を変更しない
- 既存Decision Scoreの意味を確認せず再定義しない
- DB改築と記事生成ロジックの大規模リファクタを同時に行わない
- Fail-Closedを維持
- API障害・Notion障害で既存データを消さない
- 履歴は追記型を基本とする
- Migrationは既存データを保持する

---

# 14. MVPで実装する範囲

## Phase 1 — 必須
1. 現行Notion DB / Persistenceコード監査
2. Decision Score semantics監査
3. Technology Intelligence DB schema確定
4. Decision History DB schema確定
5. Adoption Status追加
6. Production Readiness追加
7. Evidence Confidence追加
8. Main Risk / Best For / Avoid For追加
9. Canonical Entity ID設計
10. Technology単位Upsert
11. History Append
12. Score / Status Change検出
13. Subscriber View設計
14. Regression Test

## Phase 2 — 商品価値
1. Tracking Eligibility
2. Change-driven Review
3. Periodic Review
4. Monthly What Changed? Summary
5. Watchlist View
6. ADOPT / TEST / WATCH / AVOID別View
7. Score上昇・下落View

## Phase 3 — 有料需要検証後
- 独自SaaS
- Advanced Search UI
- Alert通知
- Team機能
- API提供
- CSV Export
- 海外版
- Enterprise機能

Phase 3を先に作ってはならない。

---

# 15. 今回「作らないもの」

以下は現在の優先対象外。

- 海外版DB
- Medium / DEV / Hashnode自動投稿
- 独自Webアプリ
- 独自課金システム
- 高度なBIダッシュボード
- AI Chat UI
- 法人Team管理
- API商品
- リアルタイム全件監視
- 全候補の永久保存
- 記事有料化

---

# 16. 商品仮説

このDBが解決する顧客課題は、

「AIニュースをもっと読みたい」

ではない。

以下である。

- 何を追えばよいかわからない
- 新しいAI技術が多すぎる
- 公式発表だけでは採用判断できない
- GitHub / Paper / Docs / HNを全部確認する時間がない
- 試すべきか、待つべきか、避けるべきか判断したい
- 半年前から評価がどう変わったか知りたい

### 商品の一言定義

**「世界のAI一次情報を横断し、日本の実務者が“何をWATCHし、何をTESTし、何をADOPTし、何をAVOIDすべきか”を判断するためのAI Technology Decision Intelligence DB」**

---

# 17. 事業戦略との整合性判定

## 無料note
整合：YES

無料記事はDiscovery / Education / Acquisitionとして維持する。

## 有料DB
整合：YES。ただし「記事蓄積DB」ではなく、Decision Intelligence DBへ変更が必要。

## 月次サマリー
整合：YES。ただし「記事まとめ」ではなく「評価変化レポート」に変更する。

## Decision History
整合：必須。

長期的な競争優位資産になる。

## 海外展開
現時点：HOLD

日本市場で課金理由を検証してから再判断する。

## 独自SaaS
現時点：NO

有料需要が証明される前に開発しない。

---

# 18. 他Chat / WORKに依頼する最終成果物

この指示書を受け取ったChatは、以下を順番に成果物として生成すること。

### 成果物1
**現行実装監査レポート**
- 現在のNotion schema
- Decision Score semantics
- Status semantics
- 保存条件
- Upsert / duplicateロジック
- Monthly Digestロジック
- 関連テスト

### 成果物2
**Gap Analysis**
- KEEP
- ADD
- CHANGE
- DEPRECATE
- MIGRATE
- RISK

### 成果物3
**Notion DB正式仕様**
- Technology Intelligence DB
- Decision History DB
- Property名
- Notion型
- 必須/任意
- 自動生成/手動
- Subscriber表示可否
- 更新ルール

### 成果物4
**Pipeline改修仕様**
- Tracking Eligibility
- Entity Resolution
- Upsert
- History Append
- Re-evaluation
- Monthly Summary
- Error handling

### 成果物5
**コード改修影響範囲**
- 対象ファイル一覧
- 関数一覧
- Environment Variables
- GitHub Actions
- Tests

### 成果物6
**Migration Plan**
- 既存Notionデータを消さない
- 既存プロパティ互換性を維持
- Rollback可能
- Test DBで確認後、本番適用

### 成果物7
**Regression Test Plan**
最低限、
- 既存記事生成が壊れていない
- 4 Quality Gatesが壊れていない
- Existing Notion persistenceが壊れていない
- 同一Technologyが重複しない
- 再評価でcurrent recordが正しく更新される
- Historyが追記される
- Status changeが正しく記録される
- 既存データが消えない
- API失敗時にFail-Closedする

を確認する。

---

# 19. 他Chatへの実行指示

この設計を盲目的に実装してはならない。

まずリポジトリの現行コード・現行Notion仕様を確認し、
**「現在の実装を壊さずに最小改修で実現する設計」**
へ落とし込むこと。

不一致があった場合は、

1. 現行コード上の事実
2. この指示書との差分
3. 推奨修正
4. 互換性リスク

を明示する。

既存仕様書より現行コードが新しい場合は、コードの実装事実を優先して監査し、仕様書側を更新候補として扱う。

ただし、事業戦略に関する以下の原則は固定とする。

- 無料note = 集客
- 有料DB + 月次サマリー = 収益商品
- 記事有料化を主モデルにしない
- DBの商品価値 = 比較 / 判断 / 履歴 / 変化
- 海外展開は後回し
- SaaS化は有料需要確認後
- 既存記事品質Pipelineを壊さない

---

# 20. 最終判断

今回のNotion DB改築は、現在の事業戦略と整合する。

ただし成功条件は、

**「記事をたくさん蓄積するDB」から
「AI技術の採用判断と評価変化を提供するDB」へ、本当に用途を変えること。**

特に以下は必須である。

1. Adoption Statusを既存Statusから分離
2. Decision Score semanticsを監査
3. Tracking EligibilityをPublication Scoreから分離
4. Technology単位のEntity管理
5. Decision History DB
6. 再評価ループ
7. What Changed?型の月次サマリー
8. Subscriber-facing ViewとInternal Viewの分離

この8点が実装されて初めて、現在の「無料note + 有料DB + 月次サマリー」という事業モデルと完全に整合する。
