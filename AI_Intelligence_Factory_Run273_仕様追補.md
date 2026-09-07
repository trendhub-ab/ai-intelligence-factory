# AI Intelligence Factory — Run273 仕様追補

更新日: 2026-09-07

本書は `AI_Intelligence_Factory_最終仕様書.md` に対するRun273の運用・安全契約追補である。既存のFact / Evidence / Decision / Publication Gateを緩和せず、無料枠優先とhuman-only公開を維持する。

## 1. Run272実Production E2Eから確定した事実

- Daily ONE-SHOTのProduction本体は成功完了した。
- 後段のPortfolio-aware Product Review、Subscriber Decision Brief Sync、Member Presentation Syncまで完走した。
- Note Ready同期では現行publication contractに一致する新規Readyが0件だった。
- 既存48件は現行publication contractとfingerprintが一致せず、旧契約Readyとして失効判定された。
- Run272の変更自体が48件を壊したのではなく、それ以前の本文・Evidence・アイキャッチ等のpublication-policy更新後に再生成されていない履歴Readyである。
- 実生成稿ではFact / Editorial / Publication / Evidenceは通過した一方、Reader Experienceのmulti-axis weakness / non-engineer access weaknessが残り、公開Readyにはしない判断が正しい。

## 2. Reader Value Retry契約

### 2.1 追加API禁止

Reader Valueだけが失敗理由の場合は、従来どおり `reader_value_review_no_retry` とし、新しいGemini retryを消費しない。

### 2.2 既存retryへの相乗り修復

別の修復可能Quality Gateにより既存retryが既に許可された場合のみ、同一retry instructionへ以下のReader Value修復を追加する。

- `multi_axis_reader_weakness`
- `non_engineer_access_failure`

修復対象は文章表面・説明順・重複・専門語密度に限定する。

禁止事項:

- Evidence、Decision、数値、制約の改変
- 新しい事実、使用経験、因果、数値の追加
- Evidenceにない比喩事実の創作
- Reader Valueだけを理由とする追加retry

目的は「追加API 0のまま、既に使うretryの歩留まりを上げる」ことである。

## 3. ONE-SHOT → private note draft 契約

### 3.1 自動化範囲

明示的な `Note Ready Article Sync` の `workflow_dispatch` は、Ready同期成功後に `Create note Draft` をdispatchできる。Daily ONE-SHOTのpost-run fan-outはこの明示的workflow_dispatch経路を利用するため、Productionからprivate note draftまで接続される。

### 3.2 コストガード

`Create note Draft` は既存のzero-VM preflightを必ず先に実行する。

- eligible Readyなし → Chrome VMを起動しない
- eligible Readyあり → preflightでpinした1件だけをprivate draft作成対象とする
- Gemini/model callは追加しない

### 3.3 公開境界

- note.comへのpublic releaseは自動化しない。
- 作成対象はprivate draftのみ。
- 公開前の最終確認と公開操作はhuman-onlyを維持する。

## 4. Publication-policy push reconciliationの安全境界

`note-ready-sync.yml` の `push` triggerはpublication-policy変更時のqueue reconciliation専用であり、private draft workflowへ進めてはならない。

Run273ではprivate draft fan-out条件を `github.event_name == 'workflow_dispatch'` に限定する。

禁止事項:

- `workflow_run` による受動二重triggerの追加
- policy change pushだけでnote Chrome VMを起動すること
- push reconciliationからnote.comを開くこと
- public releaseの自動化

## 5. 運用上の優先順位

1. Reader Valueを理由にGateを緩めない。
2. 既存retryの費用対効果だけを上げる。
3. Readyが存在する時だけprivate draftまで自動化する。
4. Ready 0ならVM費用も発生させない。
5. 公開は人間が最終判断する。

この順序により、顧客満足度・記事品質・無料枠維持・運用自動化を同時に守る。
