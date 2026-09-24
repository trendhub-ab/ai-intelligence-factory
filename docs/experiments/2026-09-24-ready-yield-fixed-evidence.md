# Ready到達率の固定Evidence反証実験（準備記録）

基準main: `f59a59d191c24bfaff8019d1b647ee7a6435c606`（2026-09-24 14:10:49 UTC）
実験ブランチ: `experiment/ready-yield-fixed-evidence-20260924`
状態: 静的実装監査まで。Gemini API実送信0件。実測Ready率・阻害原因は未確定。

## 読み取った現行契約

- Writerの基準プロンプトは `content_generation_protocol.py`、Productionの重ね合わせは `production_pipeline.py` の `install_runtime_layers`。編集スタイルは `classic`、`human_narrative`、`duo_narrative`。
- 記事モデル集合は `gemini-3.6-flash`、`gemini-3.5-flash`、`gemini-3.7-flash`、`gemini-3.8-flash`。現行cold-start順序は3.6、3.5、3.7、3.8で、実送信後はprovider healthによって変わる。
- `generate_intelligence_report` はEvidence preflightのあとWriterを呼び、生成原文の解析、Japanese polish、structure polish、Fact、Editorial、Publication、Human Appeal、reason disposition、deterministic rescue、dynamic retry、最終原稿整形を経る。
- Evidence不足はGemini送信前に停止する。Actionが強まるとEvidenceを再判定する。
- Quality Gate PASS後もNotion persistenceが失敗すればReadyにならない。さらにContent DB Readyとnote同期可能状態は別契約。
- `persist_results=False` は非永続A/B比較の入口で、Notion更新を避けるがReadyの実保存成功を証明しない。
- 直近mainのWorkflow Reference Guard、Repository-wide Falsification Guard、Synthetic Regression Suite、Notion Access Policy GuardはSUCCESS。

## 実験プロトコル

1. 一次情報と利用可能な原稿対象を読み取りで取得し、Evidence本文、URL、取得時刻、SHA-256、source_infoとmetadataを凍結する。Evidence Gateを変更せず、十分性を確認する。一次資料不足ならAPIを使用せず別の対象を選ぶ。
2. 最初の条件は4 Writer（classic、human_narrative、duo_narrative、Evidence中心の最小Writer）×2モデル（空き枠の多い3.6と3.5を優先）×2反復、計16初稿を上限とする。モデルごとの実際の利用可能枠と503を送信前に確かめ、対象を縮小する場合は事前に記録する。
3. 原稿のAPI生レスポンス、parse結果、polish後本文、各GateのPASS/FAILとreason、reason disposition、postprocess後の本文hashを原稿IDごとに保存する。Gateと閾値はmainの現行コードのまま使う。
4. FAIL条件ではGateの実reasonだけを用い、同じEvidenceで原則1回のfeedback再生成。再生成本数は最大8を初期上限とし、評価可能なFAILの分布を見て割り振る。APIを自己採点に使用しない。
5. Retryとdeterministic rescueの前後にGate再評価を掛け、救済前のfailure解消、別Gate破壊、Evidence・Factの劣化、本文の削除量を記録する。
6. Notion、note、GitHub公開への書込みを遮断した実行で、現行Ready保存経路の外部保存結果のみ明示的にstub化する。計測値を「Gate到達率」と「保存成功を仮定したReady適格率」に分け、実際の本番Ready到達率と混同しない。
7. 原因が再現した場合に限りfailing test→最小修正→対象・全回帰→CIを実施する。mainへ直接変更しない。

## 停止理由

この実行環境に`GEMINI_API_KEY`は渡されていない。GitHub連携はrepo読取り・ブランチ作成に対応する一方、Actionsのworkflow_dispatch操作は提供していない。ブラウザーのGitHubログイン要求は自動承認審査により却下された。現段階でAPI実験を実行したと装うことはできない。認証経路が解決するまで生成本数・Gate率・阻害原因は未測定である。
