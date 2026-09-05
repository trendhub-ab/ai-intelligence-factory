# Run237 — Product Delivery Maintenance Modularization

## Purpose

`pipeline.py`の肥大化を、記事品質・Gemini無料枠・Screening/Deep Dive・Notion契約を変えずに段階的に解消する。

Run237は、記事生成本体から独立している次の運用保守ロジックを`product_delivery_maintenance.py`へ抽出する。

- Evidence Health maintenance
- paid subscriber Technology DB sync orchestration
- monthly Digest reconciliation target selection
- monthly Digest creation orchestration
- month period helper

`process_article_backlog()`、Product ReviewのGemini処理、Screening、Deep Dive、記事品質Gateは対象外とする。

## Canonical ownership

Run237以降のcanonical ownerは`product_delivery_maintenance.py`。

- `previous_month_id(today)`
- `current_month_id(today)`
- `monthly_digest_targets(local_today)`
- `run_evidence_health_maintenance(...)`
- `run_product_delivery_maintenance(...)`

新moduleはprovider/clientをimportせず、network・Notion・logger・clock等をdependency injectionで受け取る。import時のcredential/client生成や外部I/Oはない。

## pipeline.py compatibility surface

既存の直接caller/testを壊さないため、`pipeline.py`には次の薄いwrapperだけを残す。

- `_previous_month_id(today)`
- `_current_month_id(today)`
- `run_evidence_health_maintenance()`
- `run_product_delivery_maintenance(today=None)`

wrapperは毎回live runtime object/flagをcanonical moduleへ渡す。これにより既存のoperator/testが`pipeline.ENABLE_REVENUE_PRODUCT_PHASE2`、`pipeline.decision_intelligence`、`pipeline.run_evidence_health_maintenance`等を一時差替えする契約も維持する。

## Preserved paid-product contracts

### Monthly Digest

- 通常日は、直近3つの完了月を新しい順で再確認する。
- 例: 2026-08-22 → `2026-07`, `2026-06`, `2026-05`。
- 月末日は上記3期間の後に当月も追加する。
- 例: 2026-08-31 → `2026-07`, `2026-06`, `2026-05`, `2026-08`。
- period IDのidempotencyにより、複数週停止後も直近期間を回復できる。
- 1期間の生成失敗は他期間を中断しない。

### Evidence Health

- Evidence Healthはzero-model / zero-Gemini maintenanceである。
- GitHubは既存README取得経路、arXivは既存API context取得経路、その他は既存limited HTTP health経路をそのまま使用する。
- HTMLの場合のReadable text化も既存契約を維持する。
- `COSMETIC_CHANGE` / `MOVED` / `MISSING`の集計意味を変更しない。
- material changeはTechnologyの`Next Review`を現在時刻へ前倒しするだけで、記事生成・Publication・Decision Score・Evidence閾値を変更しない。
- health recordの`rereview_triggered`はmaterial時のみtrue。
- 個別candidateの例外はerrorsへ記録し、他candidateのhealth checkを継続する。

## Protected contracts / Non-goals

Run237では以下を変更しない。

- Gemini model / fallback順
- RPD / RPM / TPM / pacing / retry budget
- Product Review request budget
- Screening候補数 / batch / calibration
- Deep Dive件数 / Backfill / Pending Retry
- Fact / Evidence / Decision / Publication / Human Appeal gate
- Evidence authority / entity binding
- Notion schema / canonical destination
- note draft/publication contract
- Daily PAUSED
- Public note release human-only

## Physical slimming result

guarded migrationはRun236 baselineの`pipeline.py`に対して次を確認してからのみ適用する。

- 4つの対象top-level definitionが各1個だけ存在する。
- Evidence Health query、subscriber sync、3期間loop、monthly digest作成のhistorical markersが対象surface内に存在する。
- `process_article_backlog()`が後続boundaryとして存在する。

条件が崩れていればfail-closedで書込みしない。

初回migration実績:

- `pipeline.py`: 13,298 lines → 13,244 lines
- 759,136 bytes → 755,724 bytes
- heavy orchestrationは`pipeline.py`から物理削除
- compatibility wrapperとlive runtime bindingのみ残存

削減行数だけを目的にせず、責務のcanonical ownershipを固定することを主目的とする。

## Falsification contract

`tests/test_run237_product_delivery_maintenance_module.py`はdependency-freeで以下を検証する。

1. monthly targetのexact order。
2. 月末current-period append。
3. disabled時のside-effect isolation。
4. subscriber / monthly individual failure isolation。
5. material Evidence changeがNext Review前倒しとhealth recordだけを行うこと。
6. provider/Gemini runtimeを新moduleが直接import/bindしないこと。
7. `pipeline.py`にheavy loop/try orchestrationが戻らずthin wrapperだけであること。

`tests/test_run237_product_delivery_maintenance_integration.py`はfull dependency環境で以下を検証する。

1. pipeline wrapperがcanonical function objectへdelegateすること。
2. live `ENABLE_REVENUE_PRODUCT_PHASE2`を毎回読むこと。
3. live `decision_intelligence`とlive Evidence Health wrapperを使うこと。
4. 既存月次period順序を維持すること。
5. Evidence Health wrapperがlive pipeline source-fetch dependencyをbindすること。

既存のRevenue Product Phase2 / Evidence Ledger / monthly Digest integrity regressionも変更せず維持する。

## Migration and rollback

`run237_product_delivery_maintenance_migration.py`を監査可能なguarded migrationとして保持する。

- current postimageへ再実行した場合はno-write。
- migration surfaceが曖昧/欠落した場合はfail-closed。
- rollbackが必要な場合も品質閾値を緩めず、canonical moduleの実装を元のpipeline surfaceへ戻すだけとする。
