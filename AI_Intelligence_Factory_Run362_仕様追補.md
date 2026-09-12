# AI Intelligence Factory Run362 仕様追補

## 目的
Gemini 503が、Gemini全体の障害ではなくProduction requestの重さ・形状に依存して発生している可能性を、最小API消費で検証する。

## 実験設計
AはRun361実測を再利用し再送しない。

- A: 軽量control（Run361）
  - gemini-3.7-flash
  - HTTP 200
  - elapsed 1.356s
  - SDK attempts=1
- B: 短縮Production相当
  - 現行 `build_decision_prompt()` を使用
  - source context 約3,000 chars
  - max_output_tokens=3,000
- C: 現行Production負荷に近い形状
  - 現行 `build_decision_prompt()` を使用
  - source context 約18,000 chars
  - max_output_tokens=`GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS`（現行既定9,000）

B/Cは同一モデル、同一runner、同一Run360 Gemini client設定で逐次実行する。

## Safety Contract
- live Gemini call: 合計2回のみ
- SDK attempts: 1 / hidden retryなし
- Factory retry/fallbackはこの診断スクリプトでは使用しない
- Notion write: なし
- note write: なし
- candidate discovery: なし
- persistence: false
- publication: なし
- prompt本文はログしない
- ログ対象: case / model / prompt chars / prompt bytes / max_output_tokens / HTTP status / elapsed / error type
- Productionと同じGemini budget concurrency groupを使用

## 判定
- A/B/Cすべて200: 単発request shapeだけでは503再現せず。連続call、実Evidence、tool利用、provider capacity等を次段で切り分ける。
- A/B=200、C=503: Production負荷形状が503発生に関与する強い証拠。
- A=200、B/C=503: Production prompt構造または出力予約量の関与が強い。
- B/Cとも503以外（429等）: quota/rate-limit系として別診断。
- B/Cが同種503: request sizeだけでなく共通Production prompt/config要因を疑う。

## Run361からの継承
Retry ownershipはFactoryのみ。SDK retryはattempts=1。Run360前Gemini-only backup `backup/gemini-only-run359-20260912` は維持する。
