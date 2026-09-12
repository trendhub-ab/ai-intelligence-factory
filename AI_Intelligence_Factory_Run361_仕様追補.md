# AI Intelligence Factory Run361 仕様追補

## 目的
Run360で導入した「Gemini retry owner = Factory / SDK attempts = 1」を、実Gemini APIへの最小送信で確認する。

## 実行契約
- モデル: gemini-3.7-flash
- logical call: 1回
- max_output_tokens: 16
- prompt: 固定短文
- SDK retry: attempts=1（追加retryなし）
- Notion書込: なし
- note書込: なし
- candidate discovery: なし
- persistence: false
- GitHub書込: なし
- timeout: Workflow全体10分
- Productionと同じ Gemini budget concurrency group を使用し、Daily/ONE-SHOTとの同時実行を防止

## 成功条件
1. `GEMINI_RETRY_OWNER == "factory"`
2. `GEMINI_SDK_RETRY_ATTEMPTS == 1`
3. `send_message` がprovider応答を返す（transport成功）
4. Notion/note/persistence副作用がない

Run361はtransport/retry ownershipの検証であり、記事生成品質の検証ではない。極小output budgetではthinking等により `response.text` が空でもHTTP transport自体は成功し得るため、本文一致は成功条件にしない。

## 2026-09-12 実測結果
- model: `gemini-3.7-flash`
- Run360 log: `owner=factory sdk_attempts=1 sdk_retries=0`
- provider request: `POST ... gemini-3.7-flash:generateContent`
- HTTP status: `200 OK`
- logical call: 1回
- elapsed: 1.356秒
- response.text: 空文字（16 token上限のため。transport failureではない）
- 503: 0
- SDK内部retry: 0
- Notion書込: 0
- note書込: 0
- persistence: false

### 判定
Run360の目的である「1 logical call = 1 SDK transport attempt」「Factoryが唯一のretry owner」は実Gemini API接続で成立した。少なくとも軽量requestではGemini 3.7 Flashは即時HTTP 200を返しており、当時のprovider全面障害仮説は支持されない。

## 失敗時
- HTTP/APIエラーはそのままfail closed。
- Run361自身ではretryしない。
- 503が返った場合も、SDK内部retryなしの単一logical callとして記録し、Run360以前との比較材料にする。

## Rollback
Run360前のGemini-only版は `backup/gemini-only-run359-20260912` に保持する。
