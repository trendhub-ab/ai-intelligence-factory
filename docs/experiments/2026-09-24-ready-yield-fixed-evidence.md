# 固定Evidence実験のRPM安全設計 v2（送信停止中）

対象: `trendhub-ab/ai-intelligence-factory` の実験ブランチ `experiment/ready-yield-fixed-evidence-20260924`。本番mainは未変更。本設計はGemini送信を再開する指示ではない。

## 実測と原因

2026-09-24の実験では、3.5と3.6に各8回を短時間で送った。各モデル7回のHTTP 503のあと、8回目はHTTP 429となった。429の構造化エラーは `GenerateRequestsPerMinutePerProjectPerModel-FreeTier`、`limit: 5` を明示した。3.7と3.8は初回がそれぞれ503となり停止した。全モデルで成功レスポンスは0、原稿0、Gate率は未測定。

原因は実験コードが本番の `_call_deep_dive_pool` を通らず、`_generate_via_chat` を直接反復したこと。本番のDeep Dive送信間隔（現在20秒）と503後のモデル制御を迂回した。RPDのpersistent counterはRPMの代用ではない。503と429は別のエラーとして記録し、503自体の原因をRPMと断定しない。

## 目標と非目標

- **目標**: 実験自身による5 RPM超過を防ぎ、同一projectのDailyと実験の送信を協調させる。Quotaに余裕がない時は原稿を減らして停止する。
- 5 RPMは今回の3.5/3.6の実測値。他モデル・tierには固定適用しない。AI Studioの現行表示と実際の429 quotaIdを優先し、未確認モデルはAPI送信を停止する。
- 外部アプリやAI Studioなど、同じprojectを使う制御外の送信までは保証できない。「429を絶対に出さない」という約束はしない。
- Evidence / Fact / Publication / Reader Value のGate、閾値、Notion・noteの状態は変更しない。

## 送信を許す条件

1. 実験開始前にproject scopeとモデルごとの実効RPMを確認し、今回5 RPMだったモデルは**共有の保守的上限3件/直近60秒**とする。実効RPMが3未満なら送信を停止し、より高い場合も実験上限を勝手に引き上げない。
2. 直近60秒の**全モデル合計**についても、project当たり25秒に1件以下の送信間隔を設ける。3.5/3.6を交互に呼んでも実験は最大約2.4件/分となる。待機は各provider試行の直前に行い、Retry・fallback・feedbackも例外にしない。
3. `runtime-state`上にproject scope・model・送信予約時刻・run ID・request IDを置く。GitHub blob SHAを使う条件付き更新と競合再読込みにより、**予約はprovider送信より前に原子的に確定**させる。予約失敗・状態読み取り失敗・scope不一致・古い状態が解釈不能なら送信しない。プロセス再起動でも直近の予約履歴を引き継ぐ。
4. Daily、本番Retry/Rescue、実験のすべてが**同じ予約入口**を使う。GitHub Actionsでは既存の `ai-intelligence-gemini-budget` concurrency groupも共有するが、それだけをRPM制御とみなさない。Gemini送信を行う他の入口が未接続なら「project全体で安全」と判定しない。
5. 一次情報固定、Evidence十分、モデル許可、既存RPD/TPM予算、共通RPM予約、provider送信の順とする。RPD上限やGate閾値は引き上げない。503を含め**送信済み予約は消さない**。提供側がカウントしたか不明な試行も、直近60秒の枠を保守的に占有させる。
6. 実験では本番の `_call_deep_dive_pool` と同一のprovider所有者を使い、比較対象モデルだけにpoolを絞る。直接 `_generate_via_chat` を呼び回す経路を廃止する。SDK内部とアプリ側で重複Retryを持たない。

## エラー時の扱い

| 応答 | 処理 | 記録 |
|---|---|---|
| 成功 | 原稿、parse前後、全Gateを保存。次の試行も共有予約を通す | provider成功本数 |
| 429 / RPM | 同一モデルの実験を直ちに中断。quotaIdとRetryInfoを記録。少なくとも `max(RetryInfo, 最古予約+65秒)` までは再開しない。自動的な即時Retryは禁止 | RPM制限で未生成 |
| 429 / RPD | モデルを当日停止。既存persistent budgetに従う | 日次上限で未生成 |
| 429 / TPM | Token制限として分離し、指定待機・token budgetを確認するまで停止 | Token制限で未生成 |
| 503 | 当該モデルの実験を初回で中断し、他モデルを試す場合も共有予約を通す。同一モデルの連続連射は禁止 | provider unavailable、Ready分母には入れない |
| 不明・状態書込み失敗 | Fail closed。自動fallbackによる追加送信をしない | operational stop |

## 実験配分

1. まず各モデル1回だけprobeする。503/429ならそのモデルの残りのセルは**未実施**と記録して止める。probeが原稿生成に成功した場合のみ、同一EvidenceでWriterごとに2反復する。
2. 同じモデルの連続送信を予約キューで平準化する。待機中にQuota・別実行の予約を再読込みし、古い事前チェック結果で送らない。
3. 失敗理由がある原稿に限りfeedbackを最大1回。再生成も同じ共有予約を通す。503/429には本文修正を依頼しない。
4. 初稿のAPI成功率、Gate通過率、Ready適格率、feedback改善率を**別の分母**で報告する。原稿が0本ならGate/Ready率を0%と表示せず「測定不能」とする。Notionを更新しない試験での実Ready到達率は主張しない。

## 検証と再開条件

2026-09-25の継続確認: 固定Evidenceのオフライン事前判定は `SUFFICIENT`。
事前判定が本番runtime-stateの起動前検査に依存して失敗する問題を実験側で修正した。
4回上限・25秒間隔・モデル別直近60秒3回・429停止・503二連続停止の
**ローカル判定器と単体テストのみ**を追加した。判定器は送信経路に未接続であり、
共有予約、残量確認、GitHub側CI、実送信は未完了。ライブ送信ガードは維持する。

2026-09-25追加: 4回までの限定実験関数 `execute_limited` を、初稿と
Gate feedback再生成の共通キューに接続した。送信前に25秒のローカル間隔と
モデル別直近60秒3回を確認し、429で全停止、503で該当モデルを止め、
503が2回連続したら全停止する。成功時はGateより先に原文を保存する。
APIを使わないテストで、この実行経路の送信回数と原文保存順を確認した。
これは**同一プロセス内の制御**であり、別ジョブやDailyと共有する原子的予約には
まだ接続していない。そのためCLIからのライブ送信拒否は維持する。

- 偽時計で `0, 25, 50, 75秒` の送信予約が直近60秒で3件を超えないこと、異なるモデル間も25秒未満で送らないこと。
- 同時2ジョブのCAS競合、プロセス再起動、状態欠落、503予約の保持、429 RetryInfo、RPD/TPM誤分類、モデルquota低下でfail closedするテスト。
- provider mockで実験の初稿・feedback・fallbackの全経路が共有予約入口を通ることを確認する。実際のGemini APIはテストに使わない。
- 対象テスト、全回帰、CIが成功するまでライブ送信は無効。送信ワークフローは現在削除済みで、実験スクリプトのlive phaseも `RPM_SAFE_EXPERIMENT_DISABLED` で停止する。
- 別途、明示的な実験実行指示があった時だけone-shot入口を用意する。PR状態変更やpushで自動発火させない。
