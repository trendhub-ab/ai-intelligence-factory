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
3. Gemini 3.7 Flashが `RUN361_OK` を返す
4. Workflow終了コード0
5. Notion/note/persistence副作用がない

## 失敗時
- HTTP/APIエラーはそのままfail closed。
- Run361自身ではretryしない。
- 503が返った場合も、SDK内部retryなしの単一logical callとして記録し、Run360以前との比較材料にする。

## Rollback
Run360前のGemini-only版は `backup/gemini-only-run359-20260912` に保持する。
