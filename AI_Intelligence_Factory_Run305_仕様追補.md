# AI Intelligence Factory — Run305 仕様追補

更新日: 2026-09-09

## Product Review Provider Runtime

Run305は、Run38の実Production反証で確認された「Product Review childだけがProduction provider/quota runtime layerを通らない」不整合を修正する。

### 現行契約

- `daily_portfolio_review.py` のProduct Review childは raw `pipeline.py` を直接起動しない。
- root pipeline entrypointは既存の `production_pipeline.py` 一つだけを維持する。
- Product Review childは `AIIF_PRODUCT_REVIEW_RUNTIME=true` を付与して `production_pipeline.py` を起動する。
- `production_pipeline.py` はこの明示modeをarticle/publication stackのimport/installより前に判定し、Product Review専用のnarrow runtimeへ分岐する。
- childはProduct Review実行前に次の順序でprovider/quota reliability layerをinstallする。
  1. `run203_runtime_state_channel.install`
  2. `gemini_timeout_rpd_fail_closed.install`
  3. `gemini_transient_recovery.install`
  4. `gemini_provider_resilience.install`
- Run203 runtime-state writabilityをchild側でもpreflightしてからGeminiを消費する。
- Run304の `AIIF_RUNTIME_STATE_BRANCH -> GEMINI_COUNTER_BRANCH` authoritative handoffを維持する。
- Run303のverified HTTP 503 contractをProduct Reviewにも実際に適用する。
- 1回目のstructured HTTP 503は既存Product Review request budget内で同一modelを1回だけ確認再試行する。
- 2回連続のstructured HTTP 503でのみ当該modelのrun-local circuitを開く。
- timeoutはHTTP 503と別扱いで、Run209のRPD fail-closed reservationを維持する。
- `production_pipeline.py` 以外のroot Python executableから `pipeline.main()` を直接呼ばない既存Repository Falsification契約を維持する。

### 変更しない契約

- Product Reviewモデル順: `gemini-3.6-flash -> gemini-3.7-flash -> gemini-3.8-flash -> gemini-3.5-flash`
- Product Review max reviews: 2
- Product Review local request budget: 3
- 各model persistent daily safety cap
- Fact / Evidence / Decision / Publication / Human Appeal Gate
- Article Deep Dive routing
- Scheduled Daily: PAUSED
- Public note release: human-only

Run260 Article Model RoutingおよびRun172のarticle/evidence/publication系overlayはProduct Review専用runtimeへ導入しない。Product Reviewの既存モデル順とpaid-product処理境界を守るためである。

詳細な実測・原因・反証契約は `docs/reference/RUN305_PRODUCT_REVIEW_PROVIDER_RUNTIME.md` を参照する。
