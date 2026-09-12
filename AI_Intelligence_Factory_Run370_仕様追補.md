# AI Intelligence Factory Run370 / Run371 仕様追補

更新日: 2026-09-12

## 目的

Run368の実復旧で `Pending Retry` へ退避した候補を、通常の新規取得・Screening・Stock作成へ戻さず、保存済み一次情報と現行Quality Gateを使って安全に再検証する。

Run370/371はGate緩和ではなく、既存のPending Retry経路に存在した到達不能・Reader Repair・モデルルーティング・503消費の契約不整合を修正する。

## 実データから判明した問題

1. `production_pipeline.py` は `pending_retry_validation` から `run_article_revalidation(..., pending_only=True)` を呼んでいたが、受け側の契約が一致していなかった。
2. 通常の `get_regen_test_items()` は `Content Status = Deep Dive` を固定条件としており、`Pending Retry` 候補を構造的に返せなかった。
3. `pipeline.py` には既に正規の `get_pending_retry_items()` が存在するため、新規DB取得ロジックを作る必要はなかった。
4. 実Pending Retry「Agent Memory as a File Format」はFact/Evidence/Publication側では通過可能だったが、Reader-only REVIEWで `reader_value_review_no_retry` となり、Run284のReader Repair認可が `current_policy_ready_recovery` 専用だったため修復されなかった。
5. Run370 workflowで `3.8 -> 3.6 -> 3.5` を明示してもRun260 install時にDEFAULT poolが前置され、実際には3.7から実行された。
6. 4-requestの小さい検証枠で同一モデルの503を2回許すと、3.7×2 + 3.8×2だけで全枠を消費し、品質修復へ到達できなかった。

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

## Run371の修正

### 明示モデル順を尊重する

通常Productionで明示設定がない場合は、従来どおり次を既定とする。

1. `gemini-3.7-flash`
2. `gemini-3.8-flash`
3. `gemini-3.6-flash`
4. `gemini-3.5-flash`

ただし、`DEEP_DIVE_MODEL_POOL` / workflow由来の明示設定が存在する場合は、その指定順を先頭から保持し、未指定の既定fallbackだけを末尾へ追加する。

Run370 read-only検証では次を明示する。

1. `gemini-3.8-flash`
2. `gemini-3.6-flash`
3. `gemini-3.5-flash`
4. 未指定既定fallbackとして `gemini-3.7-flash`

この変更はモデル別quota、persistent safety cap、Deep Dive request budget、Quality Gateを変更しない。

### 503の小予算検証向けcooldown

通常Productionの一時503 policyは従来どおり「同一モデル2回目の503でrun-local cooldown」とする。

明示的な小予算検証レーンでは `GEMINI_TRANSIENT_503_COOLDOWN_THRESHOLD=1` を設定可能とし、同一モデルが最初の503を返した時点でそのRun中だけcooldownへ入れる。

- 成功扱いにはしない。
- quota/Gateを緩和しない。
- 別モデルへ早くfallbackするためだけに使う。
- 環境変数で2より大きい値を指定してもProduction defaultより緩くできない。
- 設定はプロセス内だけで永続化しない。

## Read-only検証契約

`pending_retry_validation` は次を固定する。

- 対象: 最大1件
- Gemini request budget: 最大4
- Reader Repair: 最大1回、Reader-only + safe Evidenceのみ
- 明示モデル順: 3.8 -> 3.6 -> 3.5 -> 3.7 fallback
- 503 cooldown: この検証プロセスのみ1回
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
11. 明示モデル設定がなければ3.7-firstを維持する。
12. 明示3.8-first設定は順序を維持する。
13. 未指定既定モデルは明示モデル群の後ろへ追加する。
14. モデル重複は除去する。
15. 通常503 thresholdは2のまま維持する。
16. 小予算検証のthreshold=1では最初の503でrun-local cooldownする。
17. threshold設定でProduction defaultより緩くできない。

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
