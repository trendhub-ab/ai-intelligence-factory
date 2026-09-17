# AI Intelligence Factory ONE-SHOT Workflow退役監査 — 2026-09-18

## 結論

PR #380の追加監査として、Run297–302およびRun413 / 414 / 416 / 418 / 425の旧ONE-SHOT Workflow入口を個別確認した。今回の退役対象は、通常Production / Scheduled Dailyの共通入口ではなく、特定記事の修復・診断・eyecatch差し替え等のために追加された履歴依存のGitHub Actions入口である。

推測による一括削除は行っていない。Run297–302はworkflow原本、trigger条件、呼出script、外部副作用、コミット履歴を照合して退役した。専用Python helperや当時の回帰testは、履歴・再現性を失わせないため現時点では削除しない。代わりに、退役済みhelperへactive workflowから再び入口を作らない回帰Guardを追加した。

生成Provider API、Notion mutation、note mutation、Scheduled Dailyは本監査では実行していない。

## Run297–302の証拠

| Workflow | trigger / 対象 | 主な副作用 | 履歴上の位置づけ | 判断 |
|---|---|---|---|---|
| `run297-298-genrec-inplace-refresh.yml` | `main`へのpushかつ`execute exact GenRec in-place refresh`を含むcommit。Netflix GenRecの固定`sync_id`と旧Publication hashを検査。 | Notion manuscript / Note Ready再同期、GCP VM start/stop、同一note非公開下書きのin-place上書き。 | 2026-09-08にexecute commit、YAML修正、asset branch修正による再実行履歴あり。 | 完了済み記事専用ONE-SHOT入口として退役。 |
| `run298-existing-draft-route-retry.yml` | `main`へのpushかつ`execute exact GenRec route retry`。Run297の固定状態を要求。 | GCP VM start/stop、既存note非公開下書き上書き・actual-note audit。 | Run297/298修復チェーンのroute retry。 | 汎用Production入口ではないため退役。 |
| `run298-existing-header-retry.yml` | `main`へのpushかつ`execute exact GenRec hover header final`。固定GenRec状態を要求。 | GCP VM start/stop、既存下書きheader差し替え・本文正規化。 | 同一GenRecのheader最終修復。 | 記事専用入口として退役。 |
| `run298-header-readonly-diagnostics.yml` | `main`へのpushかつ`execute exact GenRec header read-only diagnostics`。 | Notion状態read、GCP VM start/stop、note DOM/headerのread-only診断。 | Run298修復用診断。 | 修復完了後の恒久入口として不要なため退役。 |
| `run299-genrec-body-structure-diagnostic.yml` | `main`へのpushかつ`execute GenRec body structure diagnostic`。 | Notion状態read、GCP VM start/stop、note body DOMのread-only診断。 | Run300前のGenRec body構造診断。 | 記事専用診断入口として退役。 |
| `run300-genrec-final-body-repair.yml` | `main`へのpushかつ`execute exact GenRec final body repair`。 | GCP VM start/stop、既存非公開下書き本文の修復・actual-note audit。 | 2026-09-08に同名execute commitが複数あり、Pillow追加後の再実行履歴あり。 | 完了済み修復ONE-SHOTとして退役。 |
| `run301-genrec-summary-restore.yml` | `main`へのpushかつ`restore GenRec summary in place`。 | preserved evidenceからsource rebase、Note Ready再同期、GCP VM、同一非公開下書きsummary復元。 | 2026-09-08にONE-SHOT追加とYAML trigger修正履歴あり。 | 記事専用復元入口として退役。 |
| `run302-genrec-publication-reconcile.yml` | `main`へのpushかつ`Run302 reconcile published GenRec`。 | 公開note page監査、Notion Note Readyを投稿済み状態へreconcile、GCP VM start/stop。公開操作自体はしない。 | 2026-09-08にpublication reconcile ONE-SHOT追加と依存修正履歴あり。 | 公開済み記事の完了後reconcile入口として退役。 |

## 残したもの

以下はWorkflow入口と同じ理由では削除しない。

- Run297–302専用Python helper。現時点では監査再現・履歴参照の価値があり、repo全体の参照ゼロを検索indexだけで証明できないため残す。
- Run297–302の専用回帰test。過去不具合と安全境界の再現証拠として残す。
- `note_ready_sync.py`、Publication Contract、共通note/Notion helper等。現行Productionと共有するため退役対象外。

追加Guard `tests/test_retired_run297_302_workflow_ingress.py` は、残したRun297–302 helperがactive `.github/workflows/*.yml|yaml` から再び呼ばれた場合にfailする。既存の `tests/test_retired_run297_302_workflows.py` は8本のWorkflowファイル自体の再導入をfailさせる。

## RubyGems旧ONE-SHOT

Run413 / 414 / 416 / 418 / 425も、RubyGems記事の個別復旧・eyecatch・summary経路として退役済み。入口Workflowだけを除去し、関連script/testは履歴・監査目的で直ちに一括削除しない。再導入防止は `tests/test_retired_rubygems_oneoff_workflows.py` で固定する。

## 運用上の意味

この整理は品質Gate、Safety、Provider routing、X統合ロジック、Ready / Publication契約を変更しない。削除したのは過去記事を再操作できる履歴専用入口であり、現行Productionを簡素化しつつ、検証可能性を保持することが目的である。
