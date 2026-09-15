# AI Intelligence Factory Run370 仕様追補

## 目的

Production ONE-SHOT Run #57 で実証された Provider Health Routing の実運用不整合を修正し、Ready 到達率を上げる。Quality / Fact / Evidence / Publication / Reader Gate は一切緩和しない。

## 実証された不具合

1. `run260_gemini_model_routing` の後に `run172_production_reliability` 等が `_call_model_pool` を置換するため、通常 Deep Dive の実行時に Run260 の Health 並べ替え・Health telemetry 捕捉が最終 Production 経路で失われる。
2. Quality Retry は Health 上位2モデルを先に切り出していたため、その2モデルが同一Run内ですでに unavailable / exhausted になっていると、3番手以降に利用可能モデルが存在しても `NoAvailableModelError` で終了する。Run #57 では 3.6 / 3.5 の circuit が開いた後、3.7 が生成成功していたにもかかわらず Quality Retry に進めなかった。

## Run370 契約

- Health 並べ替えは、後段 provider wrapper に置換されない Deep Dive entrypoint で毎回適用する。
- 呼び出し先はインストール時の古い `_call_model_pool` ではなく、実行時点の `pipeline_module._call_model_pool` とする。
- Quality Retry は `Health順位 → SESSION_UNAVAILABLE_MODELS / SESSION_EXHAUSTED_MODELS を除外 → 最大2 distinct models` の順で決定する。
- 最大2モデルという既存の Quality Retry provider-visible fan-out 上限は維持する。
- Fresh Deep Dive の既存 request budget / persistent RPD / circuit breaker は維持する。
- `GEMINI_USAGE_AUDIT.records` の実 success/error は Deep Dive entrypoint の finally で回収する。
- 同一 audit record の二重取り込みは timestamp/model/kind/outcome/error_type の identity で除外する。
- Health state は `runtime-state:.runtime/gemini_provider_health.json` に最大200件保存し、prompt、記事本文、候補contextは保存しない。
- Health state read/write failure は fail-open とし、記事生成そのものを停止しない。
- Screening、Evidence、Fact、Editorial、Publication、Human Appeal、Reader、Final Surface の判定基準は変更しない。
- Scheduled Daily は PAUSED のまま維持する。

## 成功条件

- Run #57 再現条件で、3.6 / 3.5 が unavailable の場合に Quality Retry が利用可能な 3.7（必要なら次点3.8）へ到達する。
- 後段 provider wrapper が `_call_model_pool` を置換した状態でも Fresh Deep Dive が Health 順に実行される。
- 後段 provider wrapper 経由の実 `GEMINI_USAGE_AUDIT` success/error が Health history に取り込まれ、次回Runへ引き継げる。
- Quality Retry は最大2モデルを超えない。
- 全回帰・Synthetic Production・Publication/Falsification Guard がPASSする。
