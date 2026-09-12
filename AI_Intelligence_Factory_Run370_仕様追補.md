# AI Intelligence Factory Run370 仕様追補

更新日: 2026-09-12

## 目的

Run368の実復旧で `Pending Retry` へ退避した候補を、通常の新規取得・Screening・Stock作成へ戻さず、保存済み一次情報と現行Quality Gateを使って安全に再検証する。

Run370はGate緩和ではなく、既存のPending Retry経路に存在した到達不能・Reader Repair契約不整合を修正する。

## 実データから判明した問題

1. `production_pipeline.py` は `pending_retry_validation` から `run_article_revalidation(..., pending_only=True)` を呼んでいたが、受け側の契約が一致していなかった。
2. 通常の `get_regen_test_items()` は `Content Status = Deep Dive` を固定条件としており、`Pending Retry` 候補を構造的に返せなかった。
3. `pipeline.py` には既に正規の `get_pending_retry_items()` が存在するため、新規DB取得ロジックを作る必要はなかった。
4. 実Pending Retry「Agent Memory as a File Format」はFact/Evidence/Publication側では通過可能だったが、Reader-only REVIEWで `reader_value_review_no_retry` となり、Run284のReader Repair認可が `current_policy_ready_recovery` 専用だったため修復されなかった。

## Run370の修正

### Pending Retry候補取得

- `pending_retry_validation` は `pipeline.get_pending_retry_items()` を使用する。
- 通常の `article_validation` は従来どおり `get_regen_test_items()` を使用する。
- 選択後にNotionページを再読込し、現在も `Content Status = Pending Retry` であることを確認する。
- `Ready`、Editorial Review、Quality Failedへ状態が変わった行はPending Retry検証対象にしない。
- 正規Pending Retry readerが存在しない場合はfail-closedする。

### Reader Repair

Run284の既存認可を、次の明示レーンだけへ拡張する。

- `current_policy_ready_recovery`
- `pending_retry_validation`

以下の全条件を同時に満たす場合だけ、モデルベースReader Repairを最大1回認可する。

- Evidence state = `SUFFICIENT`
- `decision_scope_safe = true`
- blockerがReader Value系だけ
- HARD blockerなし
- Fact / Evidence / Publication blocker混在なし
- repairable labelが既知のReader系理由コードに一致
- 同一プロセス内でReader Repair未使用

通常の新規候補、Fact混在、Evidence不足、HARD blockerは従来どおり `reader_value_review_no_retry` のままとする。

## Read-only検証契約

`pending_retry_validation` は次を固定する。

- 対象: 最大1件
- Gemini request budget: 最大4
- `persist_results = false`
- Notion本文・Article Status・Content Statusを書き換えない
- Note Ready同期を行わない
- note下書き生成・公開を行わない
- 現行Fact / Evidence / Editorial / Reader / Human Appeal / Publication Gateをすべて維持

## 回帰テスト

最低限、以下を固定する。

1. Pending Retry専用readerを使い、通常regen readerを使わない。
2. 現在状態を再読込してstale候補を除外する。
3. Reader-only + safe Evidenceのみ1回Repair可能。
4. 2回目のReader Repairは禁止。
5. HARD blockerはRepair不可。
6. Fact + Reader混在はRepair不可。
7. Evidence不足はRepair不可。
8. 通常新規候補はRepair不可。
9. 既存 `current_policy_ready_recovery` の認可は維持。
10. read-only検証では永続化しない。

## 次工程: Pending Retry Recovery

Read-only検証で accepted が実証された後にのみ、別の明示ONE-SHOTとして書込みRecoveryを有効化する。

予定する安全契約:

- 対象は現在もPending Retryの同一1件のみ
- 同一Notion page idを使用
- `persist_results = true`
- Readyをcontroller側から強制しない
- canonical Gate / persistenceのみがReady遷移を決定
- 書込み後にArticle Statusを再読込
- 現行Publication Contractのbyte-valid manuscript blockを再読込確認
- 両方を満たした場合だけ `recovered=1`
- branch版Publication ContractでNote Ready同期を行わない
- note下書き・公開を行わない

## 禁止事項

- Gate閾値緩和
- unsupported claimの温存
- 既存コメント系プロパティの一括上書き
- Product Review provider変更
- Daily再開
- note公開
- branch Publication ContractでのNote Ready一括同期
