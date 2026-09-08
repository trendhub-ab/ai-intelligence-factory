# AI Intelligence Factory — Run304 仕様追補

最終更新: 2026-09-09  
Production Source of Truth: `main`  
対象: Portfolio-aware Product Review / Gemini Persistent Counter Authority

## 1. Production事実

Run37の実API Full ONE-SHOTでRun303のHTTP 503回復を確認した一方、後段のPortfolio-aware Product Review childだけが `Persistent Gemini Daily Counter(...): 0` を表示した。親Production processは同じrunで非ゼロのcurrent counterを使用していた。

原因は、親Productionがauthoritative counterを `runtime-state` branchへ保存するのに対し、`daily_portfolio_review.py` が直接起動する `pipeline.py` childは `production_pipeline.py` のruntime-state overlayを通らず、staleな `GEMINI_COUNTER_BRANCH=main` をそのまま継承していたことである。

## 2. Run304契約

- `AIIF_RUNTIME_STATE_BRANCH` が存在する場合、Product Review childの `GEMINI_COUNTER_BRANCH` は必ずその値へ揃える。
- 現Productionのauthoritative runtime branchは `runtime-state`。
- `AIIF_RUNTIME_STATE_BRANCH` がないstandalone/operator実行では、明示された `GEMINI_COUNTER_BRANCH` を保持する。
- childのcounter authority修正だけであり、Gemini request ceilingを増やさない。
- Product Review request budget、Deep Dive/Pending Retry budget、per-model daily safety capは変更しない。
- Fact / Evidence / Decision / Publication / Human Appeal Gateは変更しない。
- Scheduled DailyはPAUSEDのまま。
- Public note公開はhuman-onlyのまま。

## 3. 回帰

`tests/test_run304_product_review_counter_state.py` をProduction回帰契約に追加する。

- stale `main`より`AIIF_RUNTIME_STATE_BRANCH=runtime-state`を優先すること。
- runtime overlayがない場合はoperator branchを壊さないこと。
- request budget 0ではchild processを起動しないこと。

詳細な反証記録は `docs/reference/RUN304_PRODUCT_REVIEW_COUNTER_STATE.md` を正本とする。