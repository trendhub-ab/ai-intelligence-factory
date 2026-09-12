# AI Intelligence Factory Run363 仕様追補

## 目的
Run362に残った時間帯需要変動の交絡を、Gemini 3.8 Flashだけで同一Workflow内に閉じて検証する。

## 実行順
1. A1 lightweight control
2. B Production-shaped request
3. A2 lightweight control

モデルは全件 `gemini-3.8-flash` 固定。Gemini 3.7は0 call。

## Safety Contract
- live Gemini call: 最大3回
- SDK attempts: 1
- SDK hidden retry: 0
- Factory retry/fallback: 使用しない
- Notion write: 0
- note write: 0
- persistence: false
- publication: 0
- candidate discovery: 0
- Production prompt本文はログしない

## B条件
現行 `build_decision_prompt()` を使用し、source context約3,000 chars、`max_output_tokens=3,000`。Run362のB相当。

## 判定
- 200 -> 503 -> 200: request shapeが503に関与する強い証拠
- 200 -> 200 -> 200: Gemini 3.8では再現せず。3.7固有capacityまたは一時的需要を疑う
- 503 -> 503 -> 503: provider high demandで交絡、request shape判定不能
- その他: mixed / inconclusive

## 継承
Run360のretry single-owner契約を維持。Run360前Gemini-only backup `backup/gemini-only-run359-20260912` は変更しない。
