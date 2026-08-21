# AI Intelligence Factory
# Notion Decision Intelligence DB 現行実装監査・Gap・正式設計

作成日: 2026-08-21  
監査対象コード基準: `AI_Intelligence_Factory_記事品質Gate校正版_2026-08-21.zip`  
最上位事業要件: `AI Intelligence Factory Notion Decision Intelligence DB 改築・実装指示書_2026-08-21.md`

> 本書は実装前の確定仕様。現時点ではDB書換え・Migration・Pipeline改修を実行しない。

---

## 0. 結論

現行Pipelineは記事品質・Evidence・Notion persistenceの安全性が高く、全面改築は不要。
一方、現行Notionは「記事/候補単位のPipeline Stock DB」であり、そのままではTechnology単位のDecision Intelligence商品にならない。

最小リスクの正式方針は次の通り。

1. **既存Internal Pipeline DBを壊さずそのまま残す。** 既存35 property、Status、Content Status、Article Status、Decision Score、Pending Retry、Quality Gate連携を維持する。
2. **商品用にTechnology Intelligence DBを新設する。** 1 Technology / Project = 1 Record。
3. **Decision History DBを新設する。** Technology Intelligence DBへのRelationで評価変化をappend-only保存する。
4. **既存Decision ScoreはAdoption Scoreへ流用しない。** 現行Decision ScoreはScreening時とDeep Dive時で意味が異なり、記事価値・話題性・Urgency・Market Impactを含むため、新規`Adoption Score`を設ける。
5. **既存`Status`の意味は変更しない。** 新規`Adoption Status = WATCH / TEST / ADOPT / AVOID`を別propertyにする。
6. **記事Stock条件Final>=60は維持する。** 商品Tracking条件とは分離する。
7. **Technology DB更新は記事Ready条件と分離する。** Evidenceに基づくDecision Assessmentが有効なら、Human Appeal/Publication Readinessで記事が落ちてもTechnology評価は更新可能にする。
8. **既存4 Quality Gatesは変更しない。** 新DBのために記事品質基準を緩和・統合しない。
9. **月次サマリーはDecision History DBのWhat Changed?へ移行する。** 現行created_timeベースの記事一覧型DigestはLegacy扱いとする。
10. **既知Technologyの再検出を「重複なので捨てる」から「Change検出候補」へ分岐する。** 新規候補の重複防止は維持する。

---

# 1. 現行実装監査

## 1.1 Repository / Regression baseline

現行配布物を横断監査した対象:

- `pipeline.py`（8,202行）
- `regression_suite.py`
- `subscription_attribution.py`
- `tests/test_pipeline_safety.py`
- `tests/test_notion_persistence.py`
- `tests/test_adversarial_regression.py`
- `tests/test_subscription_attribution.py`
- `.github/workflows/daily.yml`
- `.github/workflows/public-db-sync.yml`
- `.github/workflows/regression-test.yml`
- `.github/workflows/regression.yml`

監査時Baseline:

- Unit: **262 / 262 PASS**
- Synthetic Regression Full: **500 / 500 PASS**
- Critical failures: **0**

このBaselineをMigration前後の互換基準とする。

## 1.2 現行Notion Internal DB schema

`preflight_notion_schema()`は以下35 propertyを必須型としてFail-Closed検証している。

- Name / title
- URL / url
- Source / select
- Engagement Score / number
- Decision Score / number
- Status / select
- Content Status / select
- Article Status / select
- Subscription Visibility / select
- Score Breakdown / rich_text
- What / rich_text
- Why Important / rich_text
- Why NOT Important / rich_text
- Who / rich_text
- Action / rich_text
- License / rich_text
- Paradigm Shift / rich_text
- Alternative Comparison / rich_text
- Migration Cost / rich_text
- Note Title / rich_text
- Eyecatch / files
- Published At / date
- Analyzed At / date
- Source Summary / rich_text
- Decision / select
- Decision Reason / rich_text
- Who Should Use / rich_text
- Who Should NOT Use / rich_text
- Future Scenario / rich_text
- Article Value / number
- Grounding Status / select
- Evidence URLs / rich_text
- Screening Score / number
- Screening Reason / rich_text
- Review Status / status

## 1.3 Status semantics

### Status（既存、変更禁止）
- `Stocked`: Decision Score = Step1 Screening Score
- `Deep Dive`: Decision Score = Step2 Deep Dive Score

### Content Status（既存、変更禁止）
- Stocked
- Deep Dive
- Quality Failed
- Pending Retry
- Persistence Failed（内部Gate History用途）

### Article Status（既存、変更禁止）
- Not Planned
- Ready
- Needs Editorial Review

### Decision（既存、Adoption Statusとは別）
- NOW
- TRY
- WATCH
- WAIT
- AVOID

これは記事/実務判断用の管理コード。新商品DBのAdoption Statusへ名称変更・上書きしない。

## 1.4 Decision Score semantics監査

### Step1 / Screening Score
`build_screening_prompt()`では、無料note＋会員向け意思決定DBの題材価値として以下を採点している。

- 技術的新規性
- 実務への即効性
- 意思決定への影響
- 話題性

したがって純粋な技術採用スコアではない。

### Step2 / Deep Dive Decision Score
`build_decision_prompt()`では以下合計100点。

- Business Impact 25
- Technical Impact 25
- Urgency 20
- Market Impact 15
- Reliability 15

採用判断要素は含むが、Urgency / Market Impactがあり、さらにStep1と採点基準が異なる。

### 正式判定
指示書の判断ルール **B** に該当。

- 現行`Decision Score`はそのまま維持。
- **新規`Adoption Score`を別設計する。**
- 過去Decision ScoreをAdoption Scoreへ移植・換算しない。

## 1.5 Screening / Calibration

- 4 Source: GitHub / Hacker News / arXiv / Product Hunt
- Screening最大200件、25件Batch
- Raw>=55のみGlobal Calibration
- Calibration failure時はRaw Scoreを維持
- Commercial Value / Shelf Life / Portfolio TopicはDecision Scoreと分離
- Article Stock条件はFinal Decision Score>=60
- Source ROIは収集配分のみを調整し、Quality Gate/Stock閾値を変更しない

## 1.6 Evidence / Deep Dive

- Primary Source解決
- Source Native / Python HTML / PDF / Official Docs
- Evidence-to-Decision Sufficiency
- Supplement
- Verification Context最大180k
- Freshness resolution
- Deep Dive
- Fact / Editorial / Publication Readiness / Human Appealの4 Quality Gates

Evidence不足時はDeep Dive APIを避ける経路があり、記事品質ロジックとして独立維持すべき。

## 1.7 Notion Persistence

### Stock save
`Final>=60`だけ`save_screening_metadata_to_notion()`で新規page作成。

### Deep Dive upgrade
Stock page IDを`upgrade_notion_page_with_report()`で同一pageへupgrade。
children先行→properties commitの2段階でReady不整合を防ぐ。

### Ready定義
**4 Quality Gatesの公開条件を満たし、Notion Persistenceも成功した場合のみReady。**

### Failure / Retry
- Quality Failed: Stock recordを消さない
- Pending Retry: transient failureをQuality Failedと混同しない
- Needs Editorial Review: internal manuscriptを同一Stock pageに保持
- Screening ReasonをRetry/Review理由で上書きしない

## 1.8 Upsert / duplicate現状

現行はTechnology単位upsertではない。

- 新規収集前にInternal DBの`URL`と`Evidence URLs`を全件取得
- `canonicalize_url()`でtracking query等を正規化
- arXiv abs/pdf/version等をidentity正規化
- HN/Product Hunt discovery aliasも候補identityへ追加
- URL identityが一致した候補はScreening前にskip

したがって、**同一Technologyの再検出は「評価更新」ではなく「重複として捨てる」**のが現行挙動。
タイトル類似だけでmergeしない安全方針は正しいので維持する。

## 1.9 Public / Member DB sync現状

`sync_public_approved_to_member_db()`は、Internal DBの

- Review Status = Public Approved
- Article Status = Ready

の両方を満たす記事だけをURLキーで会員DBへcreate/updateする。
条件を外れた既存copyはarchiveする。

これは「公開承認済み記事の安全なmirror」としては適切だが、WATCH/TEST/ADOPT/AVOIDを含むDecision Intelligence商品には適さない。

## 1.10 Monthly Digest現状

- Notion `created_time`で「当月新規Stockページ」を集計
- Deep Dive Ready一覧
- Stock Top10
- Source/Status件数

つまり現状は**What Changed?ではなく当月追加記事/Stock一覧**。
前月Stock→当月Deep Dive等の変化も当月Digestに正しく反映されない。

## 1.11 Re-evaluation現状

一般TechnologyのChange-driven / Periodic Reviewは存在しない。

- Pending Retry = transient failure recovery
- Stale check = 最終Ready記事の経過日数警告
- Known URL = duplicate skip

したがって「評価が変化した技術」を蓄積するループがない。

---

# 2. Gap Analysis

| 区分 | 項目 | 現状 | 正式方針 |
|---|---|---|---|
| KEEP | Internal Pipeline DB | 記事/候補単位、35 property | 変更しない |
| KEEP | Decision Score | Step1/Step2混在だが既存運用中 | 意味変更せず互換維持 |
| KEEP | Status / Content Status / Article Status | Pipeline制御 | 絶対にAdoption用途へ流用しない |
| KEEP | Screening / Calibration | 安定運用 | Article pathとして維持 |
| KEEP | Evidence / 4 Quality Gates | 高品質記事の安全装置 | 変更しない |
| KEEP | Pending Retry / Persistence | Fail-Closed | 維持 |
| ADD | Technology Intelligence DB | なし | 新設 |
| ADD | Decision History DB | なし | 新設 |
| ADD | Adoption Score | なし | 新設。Decision Scoreから独立 |
| ADD | Adoption Status | なし | WATCH / TEST / ADOPT / AVOID |
| ADD | Production Readiness | なし | LOW / MEDIUM / HIGH |
| ADD | Evidence Confidence | なし | LOW / MEDIUM / HIGH |
| ADD | Canonical Entity ID | URL aliasのみ | Technology upsert keyとして新設 |
| ADD | Main Risk / Best For / Avoid For |類似fieldはある| 商品向けに明示property化 |
| ADD | Tracking Eligibility | Final>=60しかStockしない | Article Stockと分離 |
| ADD | History append | なし | meaningful changeのみappend |
| CHANGE | Known entity再検出 | duplicate skip | new candidateはskip、tracked entityはchange検出へ |
| CHANGE | Member DB | Ready+Approved記事mirror | Technology decision productへ切替 |
| CHANGE | Monthly Digest | 新規Stock一覧 | History由来What Changed? |
| MIGRATE | 既存記事/Stockデータ | URL単位 | Canonical Entity IDで安全にseed |
| DEPRECATE | 旧記事型Public Sync | product本体には不適 | 新DBcutover後にLegacy化 |
| DEPRECATE | 旧Monthly Digest | 商品価値が弱い | 新History Digest成功後にLegacy化 |
| RISK | Decision Score流用 | 過去互換破壊 | 禁止 |
| RISK | fuzzy entity merge | 異なる技術の誤統合 | タイトル類似merge禁止 |
| RISK | 全件毎日再評価 | Gemini quota浪費 | Change-driven + Periodic + cap |
| RISK | Migration update | 既存原稿/Status消失 | Internal DBはread-only migration source |

---

# 3. 正式DB仕様

## 3.1 論理構成

### DB-0: Existing Internal Pipeline DB
**既存のまま維持。**
記事生成、Stock、Retry、Quality Gate、Ready、内部レビューのSource of Truth。
商品DBへ改造しない。

### DB-1: Technology Intelligence DB
**有料商品の本体。**
1 Technology / Project = 1 Record。

### DB-2: Decision History DB
**評価変化の長期資産。**
DB-1へのRelationでappend-only履歴を保持。

> 商品としてはDB-1 + DB-2の2DB。既存Internal Pipeline DBは運用基盤として別責務で残す。この3論理DB構成が既存記事品質を壊さない最小リスク構成。

## 3.2 Technology Intelligence DB property

### Subscriber-facing core

| Property | Notion型 | 必須 | 生成 | Subscriber | 更新ルール |
|---|---|---:|---|---:|---|
| Technology / Project Name | title | YES | Auto | YES | entity名変更時 |
| Primary URL | url | YES | Auto | YES | 公式primary変更時 |
| Source | multi_select | YES | Auto | YES | source signal追加時 |
| Category | select | YES | Auto | YES | current portfolio topicを初期利用 |
| Adoption Score | number | Assessed時YES | Auto | YES | 再評価時 |
| Adoption Status | select | Assessed時YES | Auto | YES | WATCH/TEST/ADOPT/AVOID |
| Evidence Confidence | select | Assessed時YES | Auto | YES | LOW/MEDIUM/HIGH |
| Production Readiness | select | Assessed時YES | Auto | YES | LOW/MEDIUM/HIGH |
| Main Risk | rich_text | Assessed時YES | Auto | YES | 最大リスク1〜2文 |
| Best For | rich_text | Assessed時YES | Auto | YES | Evidence grounded |
| Avoid For | rich_text | Assessed時YES | Auto | YES | Evidence grounded |
| Short Rationale | rich_text | Assessed時YES | Auto | YES | 1〜3文 |
| First Seen | date | YES | Auto | YES | 初回のみ |
| Last Reviewed | date | Assessed時YES | Auto | YES | 再評価時 |
| Previous Score | number | 任意 | Auto | YES | 変更前score |
| Score Change | number | 任意 | Auto | YES | current-prev |
| Last Change At | date | 任意 | Auto | YES | meaningful change時 |
| Related Article | url | 任意 | Auto/Manual | YES | note URL確定後 |
| Primary Evidence URLs | rich_text | YES | Auto | YES | canonical evidence list |

### Internal-only

| Property | Notion型 | 必須 | Subscriber | 用途 |
|---|---|---:|---:|---|
| Canonical Entity ID | rich_text | YES | NO | Technology upsert key |
| Entity Resolution Status | select | YES | NO | RESOLVED / AMBIGUOUS / LEGACY_PENDING |
| Entity Aliases | rich_text | 任意 | NO | canonical URL aliases |
| Tracking Status | select | YES | NO | ACTIVE / PAUSED / ARCHIVED |
| Tracking Eligibility | checkbox | YES | NO | product tracking判定 |
| Tracking Reason | rich_text | 任意 | NO | tracking理由 |
| Assessment State | select | YES | NO | SCREENED / ASSESSED / LEGACY_PENDING |
| Last Evidence Update | date | 任意 | NO | evidence change時 |
| Next Review | date | 任意 | NO | periodic review |
| Pipeline Status | select | 任意 | NO | latest Stocked/Deep Dive等 |
| Content Status | select | 任意 | NO | latest internal state |
| Article Status | select | 任意 | NO | latest article state |
| Screening Score | number | 任意 | NO | latest final screening |
| Screening Reason | rich_text | 任意 | NO | latest reason |
| Source Summary | rich_text | 任意 | NO | latest source summary |
| Published At | date | 任意 | NO | latest primary publish date |
| Analyzed At | date | 任意 | NO | latest pipeline observation |

## 3.3 Adoption Score semantics

**Decision Scoreとは完全分離する。**
Popularity / Buzz / News UrgencyはAdoption Scoreへ入れない。

同一Deep Dive callのMANAGEMENT DATAに小さな追加fieldとして出力し、追加Gemini requestを発生させない。

推奨100点内訳:

- Evidence Quality: 25
- Production Maturity: 25
- Use-case Utility / Fit: 20
- Reliability / Security Risk: 15
- Integration / Migration Feasibility: 10
- Ecosystem / Support Durability: 5

Validator条件:

- 各component 0〜上限、合計一致
- Evidence不足なのに高scoreを許可しない
- Production Readiness LOWでADOPTを許可しない
- AVOIDにはMain Risk / Change Reason相当の根拠必須
- ADOPTはEvidence Confidence HIGHかつProduction Readiness HIGHを原則必要条件とする
- scoreだけでStatusを決めない

## 3.4 Adoption Status

### WATCH
重要だがEvidence・成熟度が不足。追跡価値あり。

### TEST
限定PoC/Sandboxで試す価値あり。本番投入は追加検証が必要。

### ADOPT
対象ユースケースで、Evidence・成熟度・リスクを踏まえ積極検討可能。

### AVOID
現時点で採用非推奨。重大な制約・Security/Reliability・成熟度・代替優位等の明示理由必須。

現行`Decision=NOW/TRY/WATCH/WAIT/AVOID`から直接コピーしない。

## 3.5 Evidence Confidence

- HIGH: Primary resolved + sufficient +重要主張/制約が一次資料で確認でき、重大な未解決矛盾なし
- MEDIUM: Primary resolved + decision成立に十分だが、単一sourceまたは制約/benchmarkの一部が限定的
- LOW: 追跡価値はあるがdecision scopeが限定的、追加Evidence待ち

`Evidence-to-Decision Sufficiency`と矛盾させない。

## 3.6 Production Readiness

- LOW: paper/prototype/preview/実装不明/本番根拠不足
- MEDIUM: 実装・docs・限定利用根拠あり、本番一般化には追加検証必要
- HIGH: stable/production useに必要な実装・運用条件・制約が一次情報で十分確認できる

## 3.7 Decision History DB

| Property | 型 | 必須 | Subscriber |
|---|---|---:|---:|
| History Entry | title | YES | NO |
| Technology | relation -> Technology DB | YES | YES |
| Reviewed At | date | YES | YES |
| Adoption Score | number | YES | YES |
| Adoption Status | select | YES | YES |
| Production Readiness | select | YES | YES |
| Evidence Confidence | select | YES | YES |
| Main Risk | rich_text | YES | YES |
| Change Reason | rich_text | YES | YES |
| Evidence Added | rich_text | 任意 | YES |
| Previous Score | number | 任意 | YES |
| Score Delta | number | 任意 | YES |
| Previous Adoption Status | select | 任意 | YES |
| Status Changed | checkbox | YES | YES |
| Snapshot Type | select | YES | NO |
| Canonical Entity ID | rich_text | YES | NO |

Snapshot Type:
- INITIAL
- CHANGE
- PERIODIC
- MIGRATION

Append条件:

- Adoption Score変化
- Adoption Status変化
- Production Readiness変化
- Evidence Confidence変化
- Main Risk変化
- 重要Evidence追加
- 月次Periodic snapshot

何も変わらなければappendしない。

## 3.8 Subscriber Views

### Default: Decision Board
表示:
- Technology / Project Name
- Adoption Status
- Adoption Score
- Production Readiness
- Evidence Confidence
- Main Risk
- Best For
- Last Reviewed

### Filter views
- ADOPT
- TEST
- WATCH
- AVOID
- Changed This Month
- Score Up
- Score Down

### Internal views
- Tracking Due
- Entity Ambiguous
- Legacy Pending Assessment
- Persistence/Sync Error

---

# 4. Pipeline改修仕様

## 4.1 原則

既存Article Pipelineを横に拡張し、置換しない。

### Existing article path
Sources → Pre-Filter → Screening → Calibration → Final>=60 Stock → Evidence → Deep Dive → 4 Quality Gates → Internal Notion → Free note

### New product path
Sources → Screening/Calibration → Tracking Eligibility → Entity Resolution → Decision Assessment → Technology DB Upsert → History Append → Re-evaluation → Monthly What Changed?

同じSource/Evidenceを再利用する。

## 4.2 Tracking Eligibility

Article Stock eligibility (`Final>=60`)は変更しない。

Phase 2で既存Screening/Calibration structured outputへ、追加requestなしで

- `TRACKING=YES/NO`
- `TRACK_REASON`

を追加する。

初期guard:

- Final>=60 → eligible
- 既存Tracked Entity再検出 → eligible
- Final 55〜59でTRACKING=YES → eligible
- Final<55の新規entity → 原則非eligible

Trackingは記事化を意味しない。

## 4.3 Entity Resolution

新規`resolve_canonical_entity_id()`を追加。

優先順位:

1. 公式GitHub repoが確認できる → `github:owner/repo`
2. arXiv paperのみ → `arxiv:<base-paper-id>`
3. Product/Framework公式URL → official domain/path由来ID
4. Product Hunt → external official URL優先、なければProduct identifier
5. HN → HN URLではなくexternal primary target

既存`candidate_identity_urls()`をAlias集合として再利用する。

**禁止:** title fuzzy similarityだけの自動merge。

ambiguity時は`Entity Resolution Status=AMBIGUOUS`とし、別recordでFail-Safe。

## 4.4 Technology DB Upsert

Upsert key = `Canonical Entity ID`。
URLではない。

- existingなし → create
- existingあり → current valuesを取得、差分計算後patch
- First Seenは上書き禁止
- Last Reviewedは評価実施時のみ更新
- Previous Scoreは更新前score
- Score Changeはnew-old
- Last Change Atはmeaningful change時のみ

Notion update失敗時に既存recordをarchive/deleteしない。

## 4.5 Decision Assessmentと記事Qualityの分離

Deep Diveの同一Gemini responseのMANAGEMENT DATAへ以下を追加する。

- Adoption Score + breakdown
- Adoption Status
- Evidence Confidence
- Production Readiness
- Main Risk

既存fieldを再利用:
- Best For <- Who Should Useを商品向けに短縮/検証
- Avoid For <- Who Should NOT Use
- Short Rationale <- Decision Reason

`Decision Intelligence Assessment Validator`を記事4 Gateとは別に追加し、Management DataだけをEvidence照合する。

Technology DB更新条件:

- Canonical Entity resolved（または明示AMBIGUOUS扱い）
- Evidence-to-Decisionが許容範囲
- Adoption fields parse/validation PASS

**Article Status=Readyを必要条件にしない。**
Human AppealやPublication Readinessだけで記事が落ちても、有効なTechnology assessmentは商品DBへ保存可能。

一方、Fact/EvidenceがTechnology assessment自体を支えない場合は更新しない。

## 4.6 Re-evaluation

現行duplicate skipを2分岐へ変更する。

- New entity: 従来どおり新規Screening path
- Existing tracked entity: duplicateとして捨てず`Change Candidate`へ

### Change-driven trigger
- 新しいofficial/evidence URL
- arXiv version/release/docs等の更新
- source metadata fingerprint変化
- 新しいSourceから同一Canonical Entityを再発見

### Periodic trigger
初期MVP推奨:
- TEST: 14日
- WATCH: 30日
- ADOPT: 30日
- AVOID: 30〜60日（reasonで調整）

全件毎日再評価しない。
`MAX_TECH_REEVALUATIONS_PER_RUN`で上限を設ける。

## 4.7 History Append transaction

推奨順序:

1. current Technology record read
2. new assessment validate
3. History append
4. Technology current record patch

History append成功・current patch失敗時は、次回reconcileできるようHistory Entryにrun/entity IDを残す。

既存データを消すrollbackは行わない。

## 4.8 Monthly What Changed? Summary

現行`created_time`ベースDigestは置換対象。
Decision History DBを対象月でqueryし、以下を生成。

1. 今月ADOPT
2. WATCH→TEST
3. TEST→ADOPT
4. 大幅上昇
5. 大幅下落
6. AVOID変更
7. 新規WATCH
8. Production Readiness変化
9. 重要Evidence追加
10. 来月優先監視
11. 今月総括
12. Recommended Next Steps

MVPは決定論的Markdown生成を基本にし、月次summaryのための追加Gemini callは必須にしない。

---

# 5. 影響ファイル一覧

## 必須改修

### `pipeline.py`
既存関数を壊さずhelper追加を中心とする。

追加/変更候補:
- env var / property constants
- `preflight_decision_intelligence_schema()` 新規
- `build_decision_prompt()` management data追加
- `_parse_gemini_response()` adoption fields追加
- `resolve_canonical_entity_id()` 新規
- `get_technology_record_by_entity_id()` 新規
- `upsert_technology_intelligence()` 新規
- `append_decision_history_if_changed()` 新規
- `validate_decision_intelligence_assessment()` 新規
- `evaluate_tracking_eligibility()` 新規（Phase2）
- `get_due_technology_reviews()` 新規（Phase2）
- `detect_tracked_entity_change()` 新規（Phase2）
- `build_monthly_digest_markdown()` / `fetch_monthly_dataset()` をHistory版へ段階移行
- `main()`にproduct side-pathを追加

**変更禁止領域:** 4 Quality Gateの閾値・判定意味、既存Notion article persistence transaction、Decision Score既存意味。

### `tests/test_notion_persistence.py`
追加:
- Technology create/update
- History append
- partial failure
- First Seen保全
- current record patch failure時の既存値保全
- internal article persistence回帰

### `tests/test_adversarial_regression.py`
追加:
- cross-source entity identity
- false merge禁止
- URL変更でもsame entity update
- same URL別entity誤merge防止
- status change/history
- no-change no-history
- AVOID reason required
- Decision Score/Adoption Score混同防止

### `tests/test_pipeline_safety.py`
追加:
- article 4 Gates完全不変
- product DB failureがnote Ready判定を壊さない
- new schema preflightがGemini消費前に失敗
- re-evaluation budget cap
- Tracking low-scoreがArticle Stock閾値をbypassしない

### `.github/workflows/daily.yml`
追加予定:
- `ENABLE_DECISION_INTELLIGENCE_DB`
- `NOTION_TECH_DATABASE_ID`
- `NOTION_TECH_DATA_SOURCE_ID`
- `NOTION_HISTORY_DATABASE_ID`
- `NOTION_HISTORY_DATA_SOURCE_ID`
- `MAX_TECH_REEVALUATIONS_PER_RUN`
- Phase2 review controls

## 条件付き改修

### `.github/workflows/public-db-sync.yml`
Phase1では変更しない。
新Technology DB cutover成功後、旧「Ready+Public Approved記事mirror」はLegacy化/停止候補。

### `.github/workflows/regression-test.yml`
Article Real Regressionは維持。
必要ならproduct DB write isolation test用modeだけ追加。

### `.github/workflows/regression.yml`
Unit追加により自動的にcoverage拡張。workflow構造は原則維持。

### `regression_suite.py`
既存Synthetic article invariantsは変更しない。
Technology DBのstate transitionはUnit/Adversarial中心。必要なら新domain fixtureを後追加。

## 原則変更不要

- `subscription_attribution.py`
- subscription metrics
- Gemini quota audit logic
- Source ROI logic

---

# 6. Migration Plan

## Stage 0 — Freeze / Backup

- Internal Pipeline DB schema/propertyを削除・renameしない
- Current member public DBも削除しない
- 本番DB export/backupを取得
- 最新コードBaseline Unit 262 + Synthetic 500を記録

## Stage 1 — Test DB作成

新規:
- Technology Intelligence TEST DB
- Decision History TEST DB

本番とは別IDでPipelineからdry-run/write test。

## Stage 2 — Schema preflight

新DB property/typeをコードでread-only検証。
欠落/型違いならGemini/API消費前にFail-Closed。

## Stage 3 — Legacy seed（read-only source）

Internal Pipeline DBを読み、Technology DBへseedする。

重要ルール:

- Internal DBはMigration中read-only
- Canonical Entity ID確定時だけ自動merge
- ambiguousはmergeしない
- First Seen = 既存created/Analyzed Atから最古値
- Decision ScoreをAdoption Scoreへコピーしない
- 既存DecisionをAdoption Statusへ自動変換しない
- Legacy recordは`Assessment State=LEGACY_PENDING`
- Adoption fieldsは再評価まで空欄可

過去に存在しないDecision Historyを捏造しない。
必要ならMigration Snapshot 1件だけappend。

## Stage 4 — Shadow Write

`ENABLE_DECISION_INTELLIGENCE_DB=true`をTEST DBに向ける。

- Existing article pipelineは従来どおり本番Internal DBへ
- Technology/HistoryだけTEST DBへ
- 3〜7回Dailyで比較

確認:
- 記事Ready件数差なし
- Quality Gate差なし
- Gemini request不必要増なし
- duplicate/History整合

## Stage 5 — Production Cutover

- Technology/History本番DB IDsへ切替
- Feature flagで即rollback可能にする
- Subscriber Viewを手動設定
- 旧Public DB syncはまだ残す

## Stage 6 — Legacy Public/Digest retire

新Technology DBとHistory Monthly Summaryが安定後のみ:

- 旧article member syncをdisable
- 旧created_time Monthly DigestをLegacy化

削除はしない。Rollback期間を設ける。

---

# 7. Regression Test Plan

## 7.1 Baseline invariants

1. Existing Unit **262/262以上**
2. Synthetic Full **500/500 / critical 0**
3. 4 Quality Gatesの既存結果不変
4. Ready = Quality pass + Existing Internal Notion Persistence success の定義不変
5. Pending Retry / Needs Editorial Review / Quality Failedの意味不変

## 7.2 Decision Score separation

- Screening Decision ScoreがAdoption Scoreへコピーされない
- Deep Dive Decision ScoreがAdoption Scoreへコピーされない
- Adoption Score missingでも既存article pathは正常
- Adoption assessment failureで記事Quality GateをFailにしない

## 7.3 Entity Resolution

- GitHub same owner/repo -> same entity
- arXiv v1/v2/pdf -> same paper entity
- HN external URL -> underlying entity
- Product Hunt -> official external entity
- same title / different URL -> mergeしない
- same entity / new URL -> current record update
- ambiguous -> separate or manual review, destructive mergeなし

## 7.4 Technology Upsert

- new entity -> 1 record create
- existing entity -> createせずpatch
- First Seen preserved
- Previous Score / Score Change correct
- no-change -> Last Change At unchanged
- failure -> prior values remain

## 7.5 History

- initial assessment -> INITIAL append
- score change -> CHANGE append
- status change -> Previous Status + Status Changed=true
- evidence only change -> append
- no meaningful change -> appendしない
- history write failure -> existing Technology dataを消さない

## 7.6 Tracking / Re-evaluation

- Tracking candidateがFinal<60でもArticle Stockへ侵入しない
- existing tracked entityはduplicate skipではなくchange evaluationへ
- unchanged tracked entityはGemini再評価しない
- due reviewだけperiodic対象
- per-run review cap厳守
- quota不足はnext runへ繰越

## 7.7 Monthly Summary

- History月次eventだけ集計
- WATCH→TEST / TEST→ADOPTを正確に分類
- score up/down correct
- AVOID change correct
- no-change daily rowsが存在しない
- member-only artifact privacy維持

## 7.8 Failure Injection

- Technology DB outage
- History DB outage
- Technology success / History failure
- History success / Technology patch failure
- Notion schema mismatch
- Entity ID collision
- API 429/503
- malformed adoption output
- Evidence insufficient

いずれも既存Internal Pipeline DBの原稿・Status・Readyを破壊しない。

---

# 8. 実装順序（正式）

## Phase 1 — Schema / Entity / Assessment / History
1. 新DB schema
2. 新env / preflight
3. Canonical Entity ID
4. Adoption Assessment fields（同一Deep Dive call）
5. Technology upsert
6. History append
7. Migration tool / dry-run
8. Subscriber View
9. Regression

## Phase 2 — Tracking / Re-evaluation / Monthly
1. Tracking Eligibility
2. Existing entity change detection
3. Periodic Review
4. History-based Monthly Summary
5. Watch/Change views
6. Regression

## Phase 3 — Demand validation後のみ
SaaS / advanced UI / alert / team / API / overseas。

---

# 9. Go / No-Go判定

**GO。**

ただし、`既存Internal DBを直接Technology DBへ意味変更する`方式はNo-Go。

理由:
- Decision Scoreが2種の意味で混在
- StatusはPipeline制御に使用中
- article manuscript / retry / quality persistenceと密結合
- URL単位recordでTechnology単位ではない

最も安全で事業要件にも合うのは、

**Existing Internal Pipeline DBを凍結維持し、Technology Intelligence DB + Decision History DBを横に追加する構成。**

これにより「無料note=集客」「有料DB+月次サマリー=収益商品」を、記事品質を壊さず段階実装できる。
