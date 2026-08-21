# AI Intelligence Factory — Decision Intelligence Phase 1 Setup

更新日: 2026-08-21

## 目的

既存 Internal Pipeline DB を変更せず、横に以下の2DBを追加する。

1. **Technology Intelligence DB** — 1 Technology / Project = 1 current record
2. **Decision History DB** — 意味のある評価変化だけを追記

既存の無料note記事Pipeline、Decision Score、Status / Content Status / Article Status、4 Quality Gatesは変更しない。

> Phase 1はFeature Flagで隔離される。`ENABLE_DECISION_INTELLIGENCE_DB=false`（既定）の間は、従来Pipelineと挙動は同一。

---

## 1. Technology Intelligence TEST DBを作る

まず本番会員DBではなく **TEST DB** として作成する。以下のProperty名・型は完全一致させる。

| Property | Notion type | Subscriber View | 備考 |
|---|---|---:|---|
| Technology / Project Name | Title | 表示 | 商品名 |
| Primary URL | URL | 表示 | 公式/Primary URL |
| Source | Multi-select | 表示 | GitHub / HackerNews / ArXiv / ProductHunt 等を累積 |
| Category | Select | 表示 | MODEL / AGENT / DEVTOOLS / INFRA / DATA / SECURITY / MULTIMODAL / PRODUCT / OTHER |
| Adoption Score | Number | 表示 | 既存Decision Scoreとは別物 |
| Adoption Status | Select | 表示 | WATCH / TEST / ADOPT / AVOID |
| Evidence Confidence | Select | 表示 | LOW / MEDIUM / HIGH |
| Production Readiness | Select | 表示 | LOW / MEDIUM / HIGH |
| Main Risk | Text | 表示 | 最大リスク |
| Best For | Text | 表示 | 適合ユースケース |
| Avoid For | Text | 表示 | 非推奨ユースケース |
| Short Rationale | Text | 表示 | 判断根拠の短文 |
| First Seen | Date | 表示 | 初回観測 |
| Last Reviewed | Date | 表示 | 最終評価 |
| Previous Score | Number | 表示 | 直前Adoption Score |
| Score Change | Number | 表示 | 現在−直前 |
| Last Change At | Date | 表示 | 意味のある変化日時 |
| Related Article | URL | 表示 | 無料note記事URL（取得できる場合） |
| Primary Evidence URLs | Text | 表示 | 一次Evidence URL群 |
| Canonical Entity ID | Text | 非表示 | Technology Upsert key |
| Entity Resolution Status | Select | 非表示 | RESOLVED / AMBIGUOUS / LEGACY_PENDING |
| Entity Aliases | Text | 非表示 | 既知URL aliasを累積 |
| Tracking Status | Select | 非表示 | ACTIVE / PAUSED / ARCHIVED |
| Tracking Eligibility | Checkbox | 非表示 | Phase 2で本格運用 |
| Tracking Reason | Text | 非表示 | 追跡理由 |
| Assessment State | Select | 非表示 | SCREENED / ASSESSED / LEGACY_PENDING / HISTORY_PENDING |
| Last Evidence Update | Date | 非表示 | Evidence変更日時 |
| Next Review | Date | 非表示 | Phase 2用 |
| Pipeline Status | Select | 非表示 | 既存Pipeline Statusのコピー |
| Content Status | Select | 非表示 | 既存意味を変更しない |
| Article Status | Select | 非表示 | 既存意味を変更しない |
| Screening Score | Number | 非表示 | 既存Screening値 |
| Screening Reason | Text | 非表示 | Screening理由 |
| Source Summary | Text | 非表示 | Source要約 |
| Published At | Date | 非表示 | 原資料公開日 |
| Analyzed At | Date | 非表示 | Pipeline分析日時 |

### Select optionの最低セット

- `Adoption Status`: WATCH / TEST / ADOPT / AVOID
- `Evidence Confidence`: LOW / MEDIUM / HIGH
- `Production Readiness`: LOW / MEDIUM / HIGH
- `Entity Resolution Status`: RESOLVED / AMBIGUOUS / LEGACY_PENDING
- `Tracking Status`: ACTIVE / PAUSED / ARCHIVED
- `Assessment State`: SCREENED / ASSESSED / LEGACY_PENDING / HISTORY_PENDING
- `Category`: MODEL / AGENT / DEVTOOLS / INFRA / DATA / SECURITY / MULTIMODAL / PRODUCT / OTHER

`Pipeline Status / Content Status / Article Status`は既存Internal DBと同じoption名を用意する。意味は変更しない。

---

## 2. Decision History TEST DBを作る

| Property | Notion type | 備考 |
|---|---|---|
| History Entry | Title | Snapshot名 |
| Technology | Relation | **Technology Intelligence TEST DBへのRelation** |
| Reviewed At | Date | 評価日時 |
| Adoption Score | Number | 新スコア |
| Adoption Status | Select | WATCH / TEST / ADOPT / AVOID |
| Production Readiness | Select | LOW / MEDIUM / HIGH |
| Evidence Confidence | Select | LOW / MEDIUM / HIGH |
| Main Risk | Text | その時点の最大リスク |
| Change Reason | Text | 変化理由 |
| Evidence Added | Text | 新規Evidence URL |
| Previous Score | Number | 直前値 |
| Score Delta | Number | 差分 |
| Previous Adoption Status | Select | 直前Status |
| Status Changed | Checkbox | Status変化有無 |
| Snapshot Type | Select | INITIAL / CHANGE / PERIODIC / MIGRATION |
| Canonical Entity ID | Text | 監査用Entity key |
| History Event ID | Text | 冪等化用。History再送時の重複追記を防ぐstable event key |

Phase 1では、INITIALまたは意味のあるCHANGEだけ自動追記する。変化なしの毎日Snapshotは作らない。

### 部分障害とHistory冪等化

- 新規Technologyはまず`Assessment State=HISTORY_PENDING`でcurrent recordを作り、INITIAL Historyの存在を確認してから`ASSESSED`へ確定する。
- Existing TechnologyはHistoryを先にappendし、その後current stateをpatchする。
- Historyには`History Event ID`を保存し、History成功後にcurrent patchだけ失敗した場合でも次Runで同じHistoryを二重追加しない。
- 同じ60→70等の遷移が将来もう一度発生した場合は、直前の`Last Change At`をtransition anchorとして別History Eventにする。Retryと将来の再遷移を混同しない。
- `HISTORY_PENDING`中に次Runの評価が変わった場合、pending currentに保存された旧評価でINITIALを復旧し、その後の新評価をCHANGEとして別途追記する。
- History Event IDが複数レコードへ衝突した場合はFail-Closedし、自動統合しない。

Decision History DBの`Technology` Relationは、必ず**Technology Intelligence TEST DBそのもの**をRelation先に指定する。

---

## 3. Decision Intelligence専用Integrationを両TEST DBへ接続する

既存Internal DB用の `NOTION_API_KEY` は変更・共有しない。Technology / History TEST DBには、Decision Intelligence専用Integrationを接続し、そのTokenを `NOTION_DECISION_INTELLIGENCE_API_KEY` として使う。

- `NOTION_API_KEY`: 既存Internal Pipeline DBのread/write専用（現行記事Pipelineを維持）
- `NOTION_DECISION_INTELLIGENCE_API_KEY`: Technology Intelligence / Decision History DB専用

Migrationは旧Internal DBを `NOTION_API_KEY` でread-only取得し、新しい商品DBのpreflight/query/create/updateは `NOTION_DECISION_INTELLIGENCE_API_KEY` で実行する。

取得できる場合はDatabase IDとData Source IDを控える。現在のPipelineはData Source IDを優先し、未設定時のみDatabase IDを使う。

---

## 4. GitHub Secrets / Variable

### Repository Secrets

- `NOTION_DECISION_INTELLIGENCE_API_KEY`
- `NOTION_TECH_DATABASE_ID`
- `NOTION_TECH_DATA_SOURCE_ID`
- `NOTION_HISTORY_DATABASE_ID`
- `NOTION_HISTORY_DATA_SOURCE_ID`

Data Source IDを使う環境ではDatabase IDを空にしてもよいが、少なくとも各DBについてどちらか一方が必要。

### Repository Variable

最初は必ず:

```text
ENABLE_DECISION_INTELLIGENCE_DB=false
```

TEST DB Schema完成後、Shadow Writeを始める時だけ:

```text
ENABLE_DECISION_INTELLIGENCE_DB=true
```

ONにした状態でSchemaが不足/型不一致の場合はGemini APIを消費する前のpreflightで停止する。

---

## 5. Legacy Migration — 必ずDry Runから

GitHub Actions → **Decision Intelligence Migration** → Run workflow。

最初は:

```text
mode = dry-run
```

Artifact `decision-intelligence-migration-...-dry-run` のJSONを確認する。

MigrationのToken分離:

- 旧Internal DB read: `NOTION_API_KEY`
- Technology / History TEST DB read/write: `NOTION_DECISION_INTELLIGENCE_API_KEY`
- 2つのTokenを相互に上書きしない

Migrationの原則:

- 既存Internal DBはread-only
- delete / archive / patchしない
- 既存Decision ScoreをAdoption Scoreへコピーしない
- 旧DecisionをAdoption Statusへ変換しない
- `Assessment State=LEGACY_PENDING`
- exact Canonical Entity IDだけ統合
- fuzzy title mergeは禁止
- AMBIGUOUSは別recordとして保持し、自動統合しない

問題がないことを確認した後だけ `mode=apply` を実行する。

---

## 6. Shadow Write確認

Migration後に`ENABLE_DECISION_INTELLIGENCE_DB=true`でDailyを1回だけ実行する。

確認項目:

1. 既存Internal DBのStock/Ready/Review/Retryが従来どおり
2. 無料note記事の本文/4 Quality Gatesに変化がない
3. Deep Diveの有効なTechnologyだけ商品DBへside-writeされる
4. `Decision Score`と`Adoption Score`が混同されていない
5. 同一Canonical EntityはTechnology current recordが増殖しない
6. Source / Evidence / Entity Aliasは再評価時に累積される
7. 意味のある変更時だけHistoryが追加される
8. Product DB write failureが記事Ready判定を巻き戻さない

---

## 7. Subscriber View（手動作成）

Phase 1ではNotion View自体をAPIで自動生成しない。TEST確認後に手動で作る。

推奨View:

- `Decision Board` — Adoption StatusごとのBoard
- `ADOPT`
- `TEST`
- `WATCH`
- `AVOID`
- `High Confidence`
- `Recently Reviewed`
- `Score Up`
- `Score Down`

Subscriber ViewではCanonical Entity ID、Pipeline Status、Retry等の内部管理列を非表示にする。

---

## 8. Rollback

問題があればRepository Variableを即時:

```text
ENABLE_DECISION_INTELLIGENCE_DB=false
```

へ戻す。

これで既存無料note PipelineはDecision Intelligence side-pathを完全に通らない。
Technology/History DBは削除せず、検証用データとして保持して原因調査する。
既存Internal DBへのMigration書込みは行っていないため、記事Pipeline側のRollback作業は不要。

---

## Phase 1でまだ行わないこと

- Tracking Eligibilityによる低Final Score候補の新規追跡
- Change-driven再評価Loop
- Periodic Review
- History由来のWhat Changed? Monthly Digest
- Subscriber向け本番DB公開
- SaaS化

これらはPhase 1のShadow Write・Migrationが安定した後のPhase 2で行う。
