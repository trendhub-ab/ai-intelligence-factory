# AI Intelligence Factory Run289 仕様追補

## 発見した状態遷移不具合

Run288はNetflix GenRecの旧Ready本文を、Geminiを使わずRun287の正しいpublication metadataへ再基底化し、current-policy `source_ready=1`まで回復した。

その後、明示的にprivate note draftを起動したが、zero-VM preflightは次を返して安全に停止した。

- `status=no_eligible_ready`
- `should_start_vm=false`
- VM/browser/draft作成は全てskip

原因をコードと実行履歴から追跡すると、Run287 merge時のpolicy reconciliationで旧GenRec Readyを失効させた際、`note_ready_sync.py`のrevocation pathが次の2項目を更新していた。

- 品質状態: `Ready` → `Ready取消`
- 投稿状態: `投稿待ち` → `取下げ`

Run288でcurrent-policy Readyへ戻った際、通常syncは品質状態を`Ready`へ戻したが、設計上Human Workflow項目である`投稿状態`は通常updateでは上書きしないため、システム自身が付けた`取下げ`だけが残った。

結果として、Content Intelligence側はcurrent-policy ReadyなのにNote Ready DB側は`Ready / 取下げ`となり、draft preflightの正しい条件 `Ready / 投稿待ち` を満たさなかった。

## Run289の判断

人間が意図的に`取下げ`や`保留`へ変更した行を一般ルールで自動復帰させてはならない。

そこでRun289は一般的な投稿状態変更ロジックを追加せず、GitHub監査履歴でRun287の自動失効対象だったことが確定しているNetflix GenRec 1件だけを対象とするone-shot migrationとする。

対象sync_id:

`3bd479ffdca9817f926aeaffbb779c4b`

## Fail-closed条件

Run289は以下をすべて満たした場合だけ`投稿状態: 取下げ → 投稿待ち`を実行する。

1. current Publication policy SHAがRun287 policy `b1b4d1e9...fd1cd45`と完全一致
2. Content Intelligence source pageが現在もReady
3. sourceがHackerNews
4. primary URLがNetflix GenRec固定slug
5. current-policy Ready manuscriptが存在
6. manuscriptに`Hacker News投稿日: 2026-08-15`が存在
7. 旧誤表示`公開・更新: 2026-08-15`が不存在
8. eyecatchが存在
9. Note Ready DBに対象sync_idが正確に1行だけ存在
10. 品質状態がReady
11. 投稿状態が正確に取下げ
12. note公開URLが空
13. 投稿日が空
14. destination/sourceのタイトルが一致
15. PATCHは投稿状態1項目だけ
16. PATCH後にNotionから読み戻し、Ready / 投稿待ちを確認
17. 読み戻し後もnote公開URL・投稿日が空

`投稿状態=保留`、`投稿済み`、既存公開URL、既存投稿日、policy driftなど、いずれかがあればfail-closedとする。

## 再実行性

既に`投稿待ち`へ復元済みの場合は`already_reactivated`として書き込み0回で正常終了する。

## private draft前の追加検証

Run288/289 ONE-SHOT workflow内でqueue復元後、VMを起動せずRun199 preflightを対象sync_id固定で実行する。

成功条件:

- status=`eligible_ready`
- should_start_vm=true
- selected_sync_id=`3bd479ffdca9817f926aeaffbb779c4b`
- zero_gemini_calls=true

このworkflow自体はprivate draftを作らず、VM/browserも起動しない。実draftは既存の明示的Note ChatOpsから別途起動する。

## コスト・公開境界

- Gemini/provider calls: 0
- 3.6残枠消費: 0
- fresh acquisition: 0
- screening: 0
- article regeneration: 0
- eyecatch regeneration: 0
- Run289内VM/browser: 0
- Run289内private draft: 0
- public note publication: 0
- Daily schedule変更: 0

## 残る一般設計課題

今回のone-shot修復とは別に、将来のpolicy reconciliationでシステム失効がHuman Workflow項目`投稿状態`を変更しないようにする一般設計修正が必要である。

これはGenRecの即時復旧と混ぜず、実private draft確認後に独立した反証可能な改修として扱う。