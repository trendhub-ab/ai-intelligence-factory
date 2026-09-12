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

## 実測結果（2026-09-12 / Run363）
- A1 lightweight: HTTP 200 / 40.255s
- B Production-shaped: HTTP 200 / 10.623s
  - prompt_chars: 16,215
  - prompt_bytes: 36,394
  - max_output_tokens: 3,000
  - response_text_chars: 2,930
- A2 lightweight: HTTP 200 / 2.946s
- SDK attempts: 全件1
- SDK hidden retry: 0
- retry owner: Factory
- Gemini 3.7 calls: 0
- live Gemini 3.8 calls: 3
- Notion write: 0
- note write: 0
- persistence: false
- publication: 0

## 実測判定
`200 -> 200 -> 200` で、Run362のB相当Production request shapeはGemini 3.8では正常通過した。

したがって、現時点では「AIIFのProduction promptが重いため、そのrequest shape自体が503を必然的に発生させる」という仮説は支持されない。Run362で3.7が返した `high demand / UNAVAILABLE` と合わせると、**3.7側の一時的capacity / high-demand状態、または3.7固有のadmission behaviorの関与がより有力**。

ただし、モデルが3.7と3.8で異なるため、これだけで3.7の503原因を単一要因へ断定はしない。A1が40.255sと長かったことからも、3.8側もその時点で低負荷とは言い切れないが、最終的には3件すべて200で完了した。

## 運用判断
- 3.7は当日の上限到達済みのため追加callしない。
- 3.8は同等のProduction-shaped requestを通過できることを実証。
- Geminiを継続利用する場合、3.8をquality repairだけでなく503時の優先fallback候補として評価する価値がある。
- ただし既存routing変更は別RunでCI・budget・品質影響を検証してから行う。

## 継承
Run360のretry single-owner契約を維持。Run360前Gemini-only backup `backup/gemini-only-run359-20260912` は変更しない。
