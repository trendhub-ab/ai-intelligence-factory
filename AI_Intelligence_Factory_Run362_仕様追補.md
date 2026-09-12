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

## 実測結果（2026-09-12 / Run362）

### A: Run361 lightweight control
- 実行時刻: 約12:47 JST
- HTTP 200
- elapsed 1.356s
- SDK attempts=1
- SDK retry=0

### B: compressed Production shape
- 実行時刻: 約12:57 JST
- model: gemini-3.7-flash
- prompt_chars: 16,212
- prompt_bytes: 36,391
- max_output_tokens: 3,000
- HTTP 503
- elapsed 4.458s
- SDK attempts=1
- retry owner: Factory
- provider message: `This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.`

### C: fuller Production shape
- 実行時刻: 約12:57 JST
- model: gemini-3.7-flash
- prompt_chars: 25,214
- prompt_bytes: 45,393
- max_output_tokens: 9,000
- HTTP 503
- elapsed 11.458s
- SDK attempts=1
- retry owner: Factory
- provider message: Bと同一のhigh demand / UNAVAILABLE 503

### 副作用
- Notion write: 0
- note write: 0
- persistence: false
- publication: 0
- live Gemini call: 2回のみ

## 判定
実測は `A=200 / B=503 / C=503`。

この結果は、**Production型request shapeが503発生に関与している可能性と整合する**。ただし因果関係はまだ確定していない。

### 重要な時間差交絡
AはRun361で約12:47 JST、B/CはRun362で約12:57 JSTに実行されており、約10分の時間差がある。今回の503自体がproviderから `currently experiencing high demand` と返されているため、その10分の間にprovider側需要・capacityが変化した可能性を排除できない。

したがって、`A=200 / B,C=503` だけを根拠に「request shapeが原因」と断定してはならない。現段階の正確な評価は以下。

- Gemini 3.7 Flashが常時503という仮説は否定方向の材料がある（Aは200）。
- Production型B/Cが同一時刻帯で503になったことは、request shape関与説を支持する材料。
- 一方で、B/C実行時だけprovider高需要だった可能性が残るため、因果は未確定。

また、B/Cではprompt長とmax_output_tokensを同時に増減しているため、仮にrequest shapeが関与していても原因を以下のどれか1つへ断定してはならない。

1. prompt/context長
2. max_output_tokensによる出力予約量
3. Production promptの命令密度・構造
4. 上記の複合負荷がprovider側の高需要時capacity admissionに不利に働くこと

CはBよりelapsedが長い（11.458s vs 4.458s）が、単発2件だけなので「重いほど遅く503になる」という統計的結論には使わない。

## 結論
- SDK hidden retry増幅説: Run360で解消済み。今回もattempts=1を実ログ確認。
- quota超過説: 今回の応答は429ではなく503 UNAVAILABLE。
- Gemini全体障害説: 軽量Aが同じ3.7 Flashで200のため単独原因としては弱いが、A/B/Cの時間差があるためprovider需要変動は未除外。
- Production request負荷関与説: **有力だが、時間差交絡のため因果未確定**。

次の最小因果検証は、同一Workflow・同一時刻帯・同一モデルで `A1（軽量）→B（Production型）→A2（軽量）` の3callを逐次実行すること。A1/A2が200でBだけ503ならrequest shape関与の証拠が大幅に強まる。3件すべて503ならprovider高需要が主因とみる。その後に必要ならprompt長とmax_output_tokensを分離する。

Productionロジックの恒久変更は、この同時刻control検証後に行う。

## Run361からの継承
Retry ownershipはFactoryのみ。SDK retryはattempts=1。Run360前Gemini-only backup `backup/gemini-only-run359-20260912` は維持する。
