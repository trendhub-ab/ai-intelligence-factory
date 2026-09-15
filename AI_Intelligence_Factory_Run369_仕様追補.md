# AI Intelligence Factory Run369 仕様追補

## 目的

note記事を実際にReadyまで到達させる確率を最優先し、Gemini記事生成モデルを固定の性能順ではなく、直近の実稼働可用性に基づいて動的に並べ替える。

この変更は品質Gateを緩和するものではない。Fact / Evidence / Publication / Human Appeal / Reader関連の判定、Deep Dive総リクエスト予算、モデル別日次予算、run-local circuit breaker、Pending Retry契約はすべて維持する。

## Cold Start

Provider Health履歴が存在しない場合の記事生成順は以下とする。

1. `gemini-3.6-flash`
2. `gemini-3.5-flash`
3. `gemini-3.7-flash`
4. `gemini-3.8-flash`

目的は最高性能モデルの優先ではなく、一定品質以上の記事を安定してReadyまで届けることにある。

## Provider Health Routing

対象はDeep Dive記事生成とmodel-based Quality Retryのみ。Screeningは対象外。

評価対象は以下4モデル。

- `gemini-3.6-flash`
- `gemini-3.5-flash`
- `gemini-3.7-flash`
- `gemini-3.8-flash`

通常は過去24時間の実API attemptを使用する。24時間内のサンプルが少ない場合は、直近N回のattemptまで古い履歴を補完して判断する。既定値は20回。

各モデルの順位はsuccess/errorからBeta(1,1)平滑化した成功率で決める。これにより1回の偶然の成功だけで過剰昇格しにくくしつつ、503・timeout等のerrorが続いたモデルは速やかに降格する。

同点時はCold Start順を使用する。

## 同一Run内の学習

同一Runで発生したGemini API結果も直ちにHealth履歴へ追加する。

例:

- 3.6が503になった場合、その後の別記事・Retryでは順位が下がり得る。
- 3.5が成功した場合、その後の別記事・Retryでは順位が上がり得る。

既存のSESSION_UNAVAILABLE_MODELS / SESSION_EXHAUSTED_MODELS / timeout circuit breakerは引き続き上位契約であり、Health Routingがこれらを解除することはない。

## Quality Retry

Quality Retryは従来どおり最大2 distinct modelsに制限する。

Provider Health Routingは「どの2モデルを使うか」を選ぶだけで、1論理Retryあたりのprovider-visible fan-outを増加させない。

## Runtime State

Provider Health履歴は既存の`runtime-state` branchに以下として保存する。

`/.runtime/gemini_provider_health.json`

保存する情報は以下のみ。

- timestamp
- model
- kind
- outcome (`success` / `error`)
- error_type

Prompt本文、記事本文、Evidence、候補タイトル、request contextは保存しない。

最大200 attemptのみ保持する。

Runtime Stateの読み書き失敗は記事生成を停止させない。Health情報は最適化データであり、Publication安全性の根拠ではないためfail-openとする。

## 環境変数

- `GEMINI_PROVIDER_HEALTH_LOOKBACK_HOURS` 既定24、1〜168時間
- `GEMINI_PROVIDER_HEALTH_RECENT_ATTEMPTS` 既定20、4〜100回

## 非変更範囲

Run369では以下を変更しない。

- Screeningモデル順
- Fact Gate
- Evidence Gate
- Publication Readiness Gate
- Human Appeal Gate
- Reader Value / Reader Quality
- Deep Dive総request budget
- モデル別RPD safety budget
- Ready判定基準
- note公開境界
- Scheduled DailyのPAUSED状態

## 事業KPI

最優先KPIは「高性能モデルを使った割合」ではなく、以下とする。

1. Deep Dive Generation Completed率
2. Ready到達率
3. note非公開下書き到達率
4. Ready 1件あたりGemini request数

Provider Health Routingは、この4指標を改善するための可用性最適化である。
