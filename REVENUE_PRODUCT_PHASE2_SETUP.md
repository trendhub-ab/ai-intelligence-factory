# AI Intelligence Factory — Revenue Product Phase 2 Setup

更新日: 2026-08-22

## 目的

Phase 2は、既存の無料note記事Pipelineを維持したまま、有料商品の中核を「記事倉庫」から「継続的な意思決定インテリジェンス」へ完成させる。

商品フローは次の4層を分離する。

1. **無料note** — 集客・認知。記事品質は既存4 Quality Gatesを維持。
2. **Technology Intelligence** — Technologyごとの現在判断。Adoption Score / WATCH・TEST・ADOPT・AVOID。
3. **Decision History** — INITIALと意味のあるCHANGEのみを蓄積。
4. **What Changed? Monthly + Subscriber Technology DB** — 会員へ安全に配布する商品面。

Legacy Migration（389→325）は既に完了している。Phase 2はMigrationを再実行・変更しない。

---

## 1. Phase 2の重要原則

- `Decision Score`（記事価値）と`Adoption Score`（導入判断）を混同しない。
- 記事にしないTechnologyでも、追跡価値があればTechnology DBへseedできる。
- Provider 503 / quota / run budget停止をSource品質の悪さとして学習しない。
- Gemini無料枠はPersistent Counter・全体Safety Capを共有し、Product Reviewだけ別の小さなrun-local枠を持つ。
- Deep Dive停止時に未試行の上位候補を捨てない。Deferred Queueへ期限付き退避し、Queue障害時はNotion Pending RetryへFail-safeする。
- SubscriberにはInternal Technology DBを直接公開しない。Sanitized DBへASSESSEDかつTracking対象だけを同期する。
- MonthlyはDecision Historyを元に生成し、Period IDで冪等化する。月末障害後も直近3完了月をcatch-up確認する。

---

## 2. Technology Intelligence DB / Decision History DB

Phase 1で作成済みの2DBをそのまま使う。Property定義は`DECISION_INTELLIGENCE_SETUP.md`のTechnology / History定義と一致させる。

Phase 2で実際に利用する状態:

- `Assessment State`: SCREENED / ASSESSED / LEGACY_PENDING / HISTORY_PENDING
- `Tracking Status`: ACTIVE / PAUSED / ARCHIVED
- `Tracking Eligibility`: true / false
- `Next Review`: 再評価スケジュール
- `Last Change At`: 意味のある変更時のみ更新

Legacy 325件は一括Gemini評価しない。`LEGACY_PENDING`のうちEntity Resolutionが`RESOLVED`のものだけを、毎Run最大1件の予約枠で段階的に評価する。AMBIGUOUS LegacyはGeminiを使わず、将来公式URL等で解決可能になった時だけ商品評価へ進める。

---

## 3. Subscriber Technology DB（別DBを新規作成）

**Internal Technology DBのViewで列を隠す方式は使用しない。** 会員配布専用DBを別に作る。

Property名と型:

| Property | Type |
|---|---|
| Technology / Project Name | Title |
| Primary URL | URL |
| Source | Multi-select |
| Category | Select |
| Adoption Score | Number |
| Adoption Status | Select |
| Evidence Confidence | Select |
| Production Readiness | Select |
| Main Risk | Text |
| Best For | Text |
| Avoid For | Text |
| Short Rationale | Text |
| First Seen | Date |
| Last Reviewed | Date |
| Score Change | Number |
| Related Article | URL |
| Primary Evidence URLs | Text |
| Canonical Entity ID | Text |

同期対象は以下をすべて満たすTechnologyだけ。

- `Assessment State=ASSESSED`
- `Tracking Eligibility=true`
- `Tracking Status != ARCHIVED`

Internal専用列（Entity aliases、Pipeline Status、Screening Reason等）はコピーしない。同一内容ならPATCHしない。Source/Evidence URLの順序差だけでは更新しない。Internalで対象外になった既知EntityはSubscriber側をarchiveするが、Subscriber DBに手動で存在する未知Entityは勝手にarchiveしない。

### Secrets / Variables

Secrets:

- `NOTION_SUBSCRIBER_TECH_DATABASE_ID`
- `NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID`（利用する場合）

Variable:

```text
ENABLE_SUBSCRIBER_TECH_SYNC=false
```

DB Schemaを作成しIntegrationを接続した後だけ`true`へ変更する。ON時はDailyのGemini呼出し前のschema preflightで型不一致をFail-Closedする。

---

## 4. Decision Monthly DB（別DBを新規作成）

Property名と型:

| Property | Type |
|---|---|
| Monthly Digest | Title |
| Period ID | Text |
| Generated At | Date |
| Change Count | Number |
| Summary | Text |

本文はDecision Historyから生成し、少なくとも以下を含む。

- Statusが変わったもの
- 評価が上がったもの
- 評価が下がったもの
- 新規で評価したもの

`Period ID=YYYY-MM`を冪等キーとして扱い、同一Periodが既に1件あれば再生成しない。2件以上存在する場合はcollisionとしてFail-Closedする。

Decision History取得はページネーションで全件取得し、10,000件Safety Limitを超えた場合は途中までの商品を作らず停止する。

Dailyごとに直近3つの完了月を確認するため、月末Workflow失敗や数週間の停止後もcatch-upできる。月末日には当月も生成対象へ追加する。

### Secrets / Variables

Secrets:

- `NOTION_MONTHLY_DATABASE_ID`
- `NOTION_MONTHLY_DATA_SOURCE_ID`（利用する場合）

Variable:

```text
ENABLE_DECISION_MONTHLY_DIGEST=false
```

DB完成・Integration接続後だけ`true`にする。

---

## 5. Phase 2 GitHub Actions設定

`daily.yml`には以下を正式設定済み。

```text
ENABLE_REVENUE_PRODUCT_PHASE2=true
TRACKING_ELIGIBILITY_MIN_SCORE=55
TRACKING_REVIEW_DAYS=14
PRODUCT_REVIEW_MAX_PER_RUN=2
LEGACY_BOOTSTRAP_MAX_PER_RUN=1
GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET=3
DEFERRED_DEEP_DIVE_MAX_PER_RUN=1
DEFERRED_DEEP_DIVE_MAX_QUEUE=20
DEFERRED_FLASH_TTL_DAYS=2
DEFERRED_TREND_TTL_DAYS=14
DEFERRED_EVERGREEN_TTL_DAYS=60
DI_MEANINGFUL_SCORE_DELTA=5
DI_STATUS_HYSTERESIS_SCORE_DELTA=3
DI_RISK_TEXT_SIMILARITY_THRESHOLD=0.82
DI_PRODUCT_TIMEZONE=Asia/Tokyo
```

Subscriber/Monthlyは安全のためWorkflow上もdefault false。

---

## 6. Gemini無料枠の予算関係

既存安全弁:

- Pipeline全体: `GEMINI_DAILY_REQUEST_BUDGET=50`
- Deep Dive model run: `12`
- Pending Retry: `2`
- Persistent model/day Safety Counter: 各モデル設定値

Phase 2追加:

- Product Review: `3` requests/run

Product Review枠はDeep Dive 12枠を消費しないが、**Pipeline全体50とPersistent model/day counterは共有する**。Persistent reserveに失敗した要求はProduct Review local budgetも消費しない。

Provider 503等でmodelがrun-local unavailableになった場合、そのRunでは同modelへ再送しない。これは候補廃棄ではなく、記事候補はDeferred / Pending、TechnologyはNext Reviewで将来再評価される。

---

## 7. Deferred Deep Dive

Deep Dive 12/12、全model unavailable、global budget停止などで未試行になった上位Backfill候補だけをDeferred Queueへ保存する。

- 翌Run最大1件復帰
- FLASH TTL 2日
- TREND TTL 14日
- EVERGREEN TTL 60日
- Queue最大20件

安全策:

- Queue保存失敗 → Notion Pending Retryへ退避
- Queue満杯で押し出された候補 → Notion Pending Retryへ退避
- Deferred処理後のQueue再保存失敗 → 残存QueueをNotion Pending Retryへ退避
- 次RunでNotion側が既にReady / Review / Quality Failed / Pending Retryならprovider再送せずQueueから除外

`regression.yml`は`deferred_deep_dive/**`をpaths-ignoreし、Queueの自己commitだけでSynthetic Regressionを再起動しない。

---

## 8. Tracking / Product Review

Screening structured outputに以下を追加する。

- `tracking_eligible`
- `tracking_reason`

記事価値と独立して判断し、AVOID判断・成熟度監視など「記事に弱いが意思決定に重要」なTechnologyを追跡可能にする。ただし無料枠保護のため自動seedはFinal Score 55以上を最低条件とする。

Product Review候補は最大2件/Run。Legacyが存在する場合は最大1件をLegacy予約枠として確保し、325件のInventoryがActive案件に永久starvationしないようにする。LegacyはRESOLVEDのみ対象。

Evidence insufficientの場合はGeminiを追加消費せず、`Next Review`を14日後へ送って毎日の再試行ループを防ぐ。

---

## 9. Meaningful Change / History

Historyを増やす条件:

- Adoption Statusの意味のある変更
- Adoption Score差が原則5点以上
- Production Readiness変更
- Evidence Confidence変更
- Evidence追加
- Main Riskの意味カテゴリ変更

WATCH↔TESTはScore差3未満ならhysteresisで状態を維持する。単なるRisk言い換えや微小スコア揺れではHistoryを増やさない。

Legacy初回正式評価は必ずINITIAL。INITIAL History Event IDはTechnology単位で安定化し、History成功→Technology patch失敗→次Runで評価文が変わってもINITIALを二重追加しない。

---

## 10. 本番導入順序

1. このReleaseをGitHubへ反映。
2. `ENABLE_DECISION_INTELLIGENCE_DB=true`は既存のまま維持。
3. Subscriber Technology DBを上記schemaで作成し、専用Integrationを接続。
4. Monthly DBを上記schemaで作成し、専用Integrationを接続。
5. Secretsを登録。
6. まず両Feature Flagは`false`のまま通常Dailyを1回実行し、Tracking/Product Review/Deferredを確認。
7. Subscriber DBを`true`にして1回実行し、sanitized内容だけが同期されることを確認。
8. Monthly DBを`true`にして1回実行し、既存Periodの冪等skip / 未生成Periodの作成を確認。
9. 問題なければ常時ON。

CTA/転換計測を利用する場合は別途`SUBSCRIPTION_LANDING_URL`を必ず設定する。未設定時は記事生成を止めないが、CTA attributionは無効のまま。

---

## Free Article Delivery Reliability（2026-08-22追加）

`daily.yml`では以下を明示設定する。

```text
ENABLE_PUBLICATION_RELIABILITY_SLOT=true
PUBLICATION_RELIABILITY_SLOTS=1
PUBLICATION_RELIABILITY_MIN_DECISION_SCORE=65
PUBLICATION_RELIABILITY_MIN_ADVANTAGE=8
ENABLE_DETERMINISTIC_PUBLICATION_RESCUE=true
```

これらはGeminiの追加無料枠を要求しない。Publication Reliabilityはmetadata-only、Deterministic Rescueは0 APIで動作する。

### 本番反映後の初回確認

Subscriber/MonthlyのFeature Flagは、専用Notion DBを作成していない場合は従来どおりOFFのままにする。

通常Dailyを縮小せず1回実行し、最低限以下を監査する。

- `[PUBLICATION RELIABILITY SLOT]` の有無と昇格候補
- Fresh候補がBacklog/Product Reviewより先にDeep Diveされること
- `[PUBLICATION RESCUE PRE-RETRY]` の発生とchanges
- `Deep Dive Ready`
- Fact / Publication / Human Appeal final state
- Gemini API Attempts / 503 / 429 / per-model persistent counter
- Product ReviewがFree Article処理後に開始されること

Ready=0の場合、ログとprivate-gate-review artifactを必ず保存し、Evidence不足・Provider障害・非修復Fact defect・Gate false-positiveのどれかへ分類する。単なる`workflow success`を記事事業の成功判定にしない。
