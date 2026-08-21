# AI Intelligence Factory — Decision Intelligence Phase 1 実装確定

作成日: 2026-08-21

## 結論

最上位事業要件に基づき、既存無料note記事Pipelineを変更せず、Technology Intelligence DB / Decision History DBをside-pathとして追加した。Feature Flagは既定OFFであり、TEST DBを準備するまで既存本番挙動は変わらない。

## 実装済み

- `decision_intelligence.py`: schema preflight / Adoption assessment / Entity Resolution / Technology upsert / Decision History append / partial-failure recovery
- `migrate_decision_intelligence.py`: Internal DB read-only legacy migration。dry-run既定、apply明示時のみTechnology seed作成
- `pipeline.py`: existing Deep Dive MANAGEMENT DATAへAdoption Score/Status等を追加し、同一Gemini call内で評価。記事本文への管理値漏洩を禁止
- `.github/workflows/daily.yml`: Feature Flag、2DB credentials、Decision Intelligence専用Tokenを追加
- `.github/workflows/decision-intelligence-migration.yml`: manual dry-run/apply migration。旧DB read Tokenと商品DB write Tokenを分離
- `tests/test_decision_intelligence.py`: 33件の専用Regression（Token分離4件を含む）
- `DECISION_INTELLIGENCE_SETUP.md`: TEST DB Schema / Secrets / Migration / Shadow Write / Rollback手順

## Notion Token分離

- `NOTION_API_KEY`: 既存Internal DB専用。既存記事Persistence / Pending Retry / Ready / Public syncの意味を変更しない。
- `NOTION_DECISION_INTELLIGENCE_API_KEY`: Technology Intelligence DB / Decision History DB専用。
- Migrationは旧DBを既存Tokenでread-only取得し、新DBだけ専用Tokenでpreflight/query/create/updateする。
- 専用Token欠落時はDecision Intelligence preflightがFail-Closedし、既存Internal Tokenへ暗黙fallbackしない。

## 保護したBusiness/Quality invariant

- 無料note = 集客
- 有料DB＋月次サマリー = 収益商品
- 既存Decision Scoreの意味を変更しない
- 既存Status / Content Status / Article Statusの意味を変更しない
- Stock Final>=60条件をPhase 1では変更しない
- 4 Quality Gates / Evidence / Retry / Ready定義を変更しない
- Product DB失敗で記事Pipelineを失敗扱いにしない
- 既存Notionデータをdelete/archive/patchするMigrationを行わない

## History安全性

1. New Technology currentを`HISTORY_PENDING`で作成
2. INITIAL HistoryをEvent IDで確認/作成
3. currentを`ASSESSED`へfinalize
4. Existingの意味ある変更はHistory-first→current patch
5. patch失敗時は同じEvent IDを次Runで再利用
6. CHANGE Event IDへ前回`Last Change At`を含め、将来同じ遷移が再発した場合は別History化
7. HISTORY_PENDING中に新評価が変われば旧pending値でINITIAL復旧→新評価をCHANGEとして追記

## 最終Validation

- Python syntax: PASS
- Safety: 76/76
- Notion Persistence: 48/48
- Adversarial: 127/127
- Subscription Attribution: 11/11
- Decision Intelligence: 33/33
- 全Unit: 295/295
- Synthetic Regression Full: 500/500
- Critical failures: 0
- Workflow YAML: 5/5
- requests timeout漏れ: 0
- pipeline.py top-level duplicate definitions: 0

## 次の運用順序

1. `DECISION_INTELLIGENCE_SETUP.md`どおりTechnology/History TEST DBを作る
2. Relation先と全Property名/型/select optionsを確認
3. GitHub Secretsを設定し、Feature Flagはまだfalse
4. Migration workflowを`dry-run`で1回実行
5. Plan artifactをレビュー
6. 問題なければ`apply`
7. `ENABLE_DECISION_INTELLIGENCE_DB=true`にしてDailyを1回だけShadow Write
8. Internal DBと記事品質が不変、商品DBのEntity/Historyが正しいことを確認
9. Phase 1を数Run観測してからPhase 2（Tracking Eligibility / Re-evaluation / What Changed? Monthly Digest）へ進む
