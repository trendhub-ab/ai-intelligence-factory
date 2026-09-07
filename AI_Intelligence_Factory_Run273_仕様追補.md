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

## 6. 多言語表示名の冪等性契約

Run272後のProduction監査で、Factory自身が生成した多言語表示ラッパーを再入力した場合に、同じ日本語カテゴリが二重に包まれる余地を確認した。Run273では `source_normalization.py` の表示正規化を冪等化する。

- 生の中国語・韓国語・Cyrillic等の原題には、従来どおり日本語カテゴリ + 原題の表示ラッパーを1回だけ付与する。
- Factory生成済みの `海外技術情報「…」` 等は再ラップしない。
- 同一カテゴリが二重にネストしている既存値は1段へ正規化する。
- 原題そのものを翻訳・改変してEntityを推測しない。
- 表示正規化はEvidence、URL、Decision、Source identityを変更しない。

これにより、再同期・再取得を繰り返しても表示名が肥大化せず、DB一覧の可読性とEntity安定性を維持する。

## 7. Product Review Gemini 3.8 fallback復元契約

Run272実Productionでは、Portfolio-aware Product Reviewが実行対象を持ちながら、当該stepの環境変数から `gemini-3.8-flash` が欠落していたため、他のFlash候補が利用不能な局面で既存の3.8 fallbackを利用できない経路を確認した。

Run273では `daily-one-shot.yml` のPortfolio-aware Product Review stepに以下を復元する。

- `GEMINI_38_FLASH_DAILY_BUDGET: "18"`
- `GEMINI_DEEP_DIVE_MODEL_CANDIDATES` に `gemini-3.8-flash` を含める
- `DAILY_PORTFOLIO_REQUEST_BUDGET: "3"` の既存run上限は維持する

安全境界:

- 有料APIへの切替は行わない。
- 3.8のper-model上限18は既存Free Tier管理と同じFail-Closed予算契約に従う。
- Product Reviewのために無制限retryを追加しない。
- Run272で導入した600秒のProduct Review時間上限を維持する。
- 3.8 fallback復元は記事Fact / Evidence / Publication Gateを緩めない。

## 8. Run273反証テスト契約

Run273の完了条件は、実装が動くことだけではなく、以下の反証を同時に満たすこととする。

- Reader-only failureが追加Gemini retryを発生させない。
- 既存Quality retryが走る時だけReader Value局所修復が相乗りする。
- pushによるNote Ready reconciliationからprivate draftへ進まない。
- explicit workflow_dispatchだけがprivate draft workflowをdispatchできる。
- private draft側のzero-VM preflightとhuman-only公開境界を維持する。
- 多言語表示ラッパーが再入力・二重入力でも冪等である。
- Product Review stepが3.8 Free fallbackとrun budget上限を同時に保持する。
- Repository-wide Falsification / Integration Reconciliation / Notion Access Policy / Workflow Reference / Live Acquisition Smokeをすべて通過する。
