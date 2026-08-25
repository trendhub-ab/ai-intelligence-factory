# AI Intelligence Factory — Revenue Product Phase 2 Release Validation

検証日: 2026-08-22 JST

## Release結論

**PASS — Revenue Product Phase 2完成版としてリリース可能。**

既存の無料note記事Pipeline、4 Quality Gates、Legacy Migration、requirementsを維持したまま、有料Decision Intelligence商品に必要なP0ロジックを実装した。Subscriber/Monthlyは別Notion DBを作成するまでFeature Flag OFFを維持する。

## 1. 回帰テスト

- Phase 2専用: **37/37 PASS**
- 全Unit（pytest）: **345/345 PASS**
- 全Unit（GitHub Workflowと同じ unittest discover）: **345/345 PASS**
- Synthetic Regression Full: **500/500 PASS**
- Synthetic critical failures: **0**
- Synthetic production write isolation: **true**
- Python compile: **11/11 files PASS**
- Workflow YAML parse: **5/5 PASS**
- duplicate literal dict key static audit: **PASS**
- `git diff --check`: **PASS**
- `migrate_decision_intelligence.py`: **baselineから変更なし**
- `requirements.txt`: **baselineから変更なし**

## 2. Deferred Deep Dive

検証済み:

- Deep Dive 12/12または全model unavailableで未試行上位候補をDeferredへ保存。
- 翌Run最大1件だけ復帰。
- TTL: FLASH 2日 / TREND 14日 / EVERGREEN 60日。
- identity dedupe。
- Queue保存失敗時はNotion Pending Retryへ退避。
- Queue capacity overflowで押し出された候補もNotion Pending Retryへ退避。
- Deferred処理後のQueue再保存失敗でも残存QueueをNotion Pending Retryへ退避。
- Notion側が既にReady / Editorial Review / Quality Failed / Pending RetryならGemini再送しない。
- Queue自己commitはSynthetic Regressionのpush trigger対象外。

判定: **候補を黙って失う経路をFail-safe化。**

## 3. Source ROI v2

検証済み:

- 503 / provider unavailable / quota / Deep Dive run budget stopをSource ROI denominatorから除外。
- Quality Failureは実質歩留まりとして残す。
- Provider障害で汚染された可能性がある旧v1 stateはv2学習へ持ち越さない。
- 既存4 Source対称性・最低取得枠の既存Regressionを維持。

判定: **Gemini障害をSource品質低下として自己学習するループを遮断。**

## 4. Tracking / Product Review / Legacy

検証済み:

- Screening outputに`tracking_eligible` / `tracking_reason`を追加。
- 記事Final 60未満でもFinal 55以上で追跡価値があればTechnology seed可能。
- AMBIGUOUSは自動seed/reviewしない。
- Product Review最大2 Technology/Run。
- Legacyが存在する場合、RESOLVED Legacy最大1件/Runを予約し、Active候補による永久starvationを防止。
- AMBIGUOUS LegacyへGeminiを使わない。
- Evidence不足時はNext Reviewを将来へ送り、毎日同じ候補を再試行しない。
- 新規SCREENED seedは初回Product Reviewを不必要に14日待たせない。

判定: **記事価値と有料DB価値を分離しつつ、無料枠を浪費しない。**

## 5. Gemini Budget競合

構造:

- Pipeline全体Safety Cap: 50 requests/run（既存）
- Deep Dive: 12 requests/run（既存）
- Pending Retry: 2 requests/run（既存）
- Product Review: 3 requests/run（Phase 2）
- Persistent model/day counter: 全用途共通（既存）

検証済み:

- Product ReviewはDeep Dive 12枠を消費しない。
- Product ReviewもPipeline全体50枠とPersistent model/day counterを必ず共有。
- Persistent reserve拒否時はProduct Review local budgetを消費しない。
- run-local unavailable modelを同Runで再度叩かない。
- Product ReviewでUnavailableになった場合も記事候補はDeferredで将来回収可能。

判定: **有料DB更新用の最低枠を持ちつつ、Free Tier Safetyを迂回しない。**

## 6. Decision History / Meaningful Change

検証済み:

- Legacy初回正式評価はINITIAL。
- INITIAL Event IDはTechnology単位で安定化し、History成功→current patch失敗→再評価内容変化でも二重INITIALを防ぐ。
- Score差5未満の微小揺れを原則CHANGE化しない。
- WATCH⇄TESTはScore差3未満でhysteresis。
- Riskの同義言い換えをCHANGE化しない。
- Readiness / Confidence / Evidence / Riskカテゴリ / Statusの実質変化をHistory化。
- HISTORY_PENDING回復の既存transaction/idempotency Regressionを維持。

判定: **月次商品がモデル揺れのノイズで埋まらない。**

## 7. Subscriber Technology DB

検証済み:

- Internal DBとは別のSanitized DBへ同期。
- `ASSESSED` + Tracking Eligibility true + 非ARCHIVEDだけ公開対象。
- Internal専用列をpayloadへ含めない。
- 新規create / changed update / unchanged no-patch / revoke archiveを検証。
- Source/Evidence URLの順序差だけではPATCHしない。
- destination duplicateはarchive。
- Internal Canonical Entity ID collisionはFail-Closed。
- Subscriber DBの未知/manual rowは勝手にarchiveしない。
- Feature Flag ON時はschema preflightをGemini前に実行。

判定: **Notion Viewの列非表示をアクセス制御として使わず、商品境界を別DBで確立。**

## 8. What Changed? Monthly

検証済み:

- Decision History起点。
- Period ID idempotency。
- Period ID duplicate collisionはFail-Closed。
- Asia/Tokyoの月境界をUTCへ正しく変換。
- History全ページpagination。
- 10,000件Safety Limit超過時は部分Digestを作らずFail-Closed。
- 直近3完了月を毎Daily catch-up確認。
- 月末は当月も対象。
- Fresh候補0件・duplicate check停止・Screening quota停止・Pending Retry quota停止でもGemini不要のProduct delivery maintenanceを可能な限り実行。

判定: **月末1回のWorkflow失敗で有料月次商品が永久欠品する経路を除去。**

## 9. Notion Schema

preflight対象:

1. Technology Intelligence DB — 36 properties
2. Decision History DB — 17 properties
3. Subscriber Technology DB — 18 properties（Feature Flag ON時）
4. Decision Monthly DB — 5 properties（Feature Flag ON時）

正常schema 4DB同時検証と、Subscriber schema不足のFail-ClosedをUnit Test化。

Subscriber/Monthly DBはこのReleaseだけでは自動作成しない。`REVENUE_PRODUCT_PHASE2_SETUP.md`に従ってNotionで作成し、Integration接続・Secrets設定後にFeature FlagをONにする。

## 10. 既存資産との整合性

- Legacy Migration 389→325のコード: **変更なし**
- 既存Internal DB semantics: **変更なし**
- Decision Score: **Adoption Scoreへ意味変更なし**
- Stock threshold 60: **記事Stockとして維持**
- Tracking minimum 55: **商品追跡seedの別条件**
- 4 Quality Gates: **緩和・削除なし**
- `requirements.txt`: **変更なし**
- 旧Internal Monthly Artifact: 運用者用として残るが、Subscriber商品MonthlyはDecision History起点の別DB。

## 11. 未自動化で意図的に残した事項

- Subscriber Technology DB / Decision Monthly DBそのもののNotion作成。
- 両DBへの専用Integration接続。
- GitHub Secrets登録。
- `ENABLE_SUBSCRIBER_TECH_SYNC=true` / `ENABLE_DECISION_MONTHLY_DIGEST=true`への切替。
- `SUBSCRIPTION_LANDING_URL`の販売導線URL設定。

これらは外部本番環境の管理操作であり、コードRelease内で勝手に実行しないことを安全仕様とする。

## 12. Release判定

**GO**

次工程はこのZIPをGitHubへ反映し、まずSubscriber/Monthly Feature Flag OFFの通常DailyでTracking / Product Review / Deferredを実運用確認する。その後、別Notion DBを作成してSubscriber→Monthlyの順に段階ONする。
