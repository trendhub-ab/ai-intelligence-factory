# 統合後の残存Run資産参照調査 — 2026-09-17

対象main: `9296c90a2f4c7953b884800ff3edda177f5cb57a`。追跡ファイル全文とAST import graphを照合した。`production_pipeline.py`からのimport closureとactive Workflow内のscript/moduleからのimport closureに、以下14専用Pythonへの経路は検出されなかった。ただし任意の動的importや外部手動実行を数学的に否定する結果ではない。

| 専用Python | 現在の直接参照（自己参照を除く） | 判断 |
|---|---|---|
| `run297_genrec_run296_rebase.py` | `tests/test_retired_run297_302_workflow_ingress.py`<br>`tests/test_run297_298_genrec_refresh.py` | 保持：テストまたは別helperから必要 |
| `run298_existing_header_replace.py` | `tests/test_run298_existing_header_replace.py` | 保持：テストまたは別helperから必要 |
| `run298_genrec_inplace_refresh.py` | `run298_existing_header_replace.py`<br>`run298_header_readonly_diagnostics.py`<br>`run298_hover_header_final.py`<br>`run299_genrec_body_structure_diagnostic.py`<br>`run300_genrec_final_body_repair.py`<br>`run301_genrec_summary_restore.py`<br>`run302_genrec_publication_reconcile.py`<br>`run418_rubygems_canonical_eyecatch.py`<br>`run425_rubygems_summary_restore.py`<br>`tests/test_retired_run297_302_workflow_ingress.py`<br>`tests/test_run297_298_genrec_refresh.py` | 保持：テストまたは別helperから必要 |
| `run298_header_readonly_diagnostics.py` | `tests/test_retired_run297_302_workflow_ingress.py`<br>`tests/test_run298_header_readonly_diagnostics.py` | 保持：テストまたは別helperから必要 |
| `run298_hover_header_final.py` | `run418_rubygems_canonical_eyecatch.py`<br>`tests/test_retired_run297_302_workflow_ingress.py`<br>`tests/test_run298_hover_header_final.py` | 保持：テストまたは別helperから必要 |
| `run299_genrec_body_structure_diagnostic.py` | `tests/test_retired_run297_302_workflow_ingress.py`<br>`tests/test_run299_genrec_body_structure_diagnostic.py` | 保持：テストまたは別helperから必要 |
| `run300_genrec_final_body_repair.py` | `run301_genrec_summary_restore.py`<br>`run425_rubygems_summary_restore.py`<br>`tests/test_retired_run297_302_workflow_ingress.py`<br>`tests/test_run300_genrec_final_body_repair.py` | 保持：テストまたは別helperから必要 |
| `run301_genrec_summary_restore.py` | `run302_genrec_publication_reconcile.py`<br>`tests/test_retired_run297_302_workflow_ingress.py`<br>`tests/test_run301_genrec_summary_restore.py` | 保持：テストまたは別helperから必要 |
| `run302_genrec_publication_reconcile.py` | `tests/test_retired_run297_302_workflow_ingress.py`<br>`tests/test_run302_genrec_publication_reconcile.py` | 保持：テストまたは別helperから必要 |
| `run413_oneoff_rubygems_manual_ready.py` | `run425_rubygems_summary_restore.py`<br>`tests/test_review_reader_summary.py` | 保持：テストまたは別helperから必要 |
| `run414_rubygems_eyecatch.py` | `run416_rubygems_zero_model_eyecatch.py`<br>`tests/test_run414_rubygems_eyecatch.py` | 保持：テストまたは別helperから必要 |
| `run416_rubygems_zero_model_eyecatch.py` | `tests/test_run416_zero_model_eyecatch.py` | 保持：テストまたは別helperから必要 |
| `run418_rubygems_canonical_eyecatch.py` | `docs/RUN418_CANONICAL_RUBYGEMS_EYECATCH.md`<br>`run419_rubygems_eyecatch_plan_repair.py`<br>`run421_rubygems_zero_model_canonical_layout.py`<br>`run422_rubygems_pinned_canonical_copy.py`<br>`run425_rubygems_summary_restore.py`<br>`tests/test_run418_rubygems_canonical_eyecatch.py` | 保持：テストまたは別helperから必要 |
| `run425_rubygems_summary_restore.py` | `tests/test_run425_summary_restore.py` | 保持：テストまたは別helperから必要 |

## テストと仕様追補

12専用testファイルはpytest自動収集で現在も実行され、過去の安全境界・既存下書き・header・summaryの回帰資産として保持する。`tests/test_review_reader_summary.py`もRun413を使用するため、記事専用入口の退役だけを理由に削除しない。

Run301/302の2仕様追補、および `docs/RUN413_ONEOFF_RUBYGEMS_MANUAL_READY.md` / `RUN414_RUBYGEMS_EYECATCH.md` / `RUN416_ZERO_MODEL_EYECATCH_FALLBACK.md` / `RUN418_CANONICAL_RUBYGEMS_EYECATCH.md` の4文書は履歴仕様・検証条件として保持する。現行入口の存在証明には使用しない。現在の入口退役状態は `2026-09-18-retired-one-shot-workflows.md` と退役Guardを参照する。

## 削除条件の判定

ユーザーの5条件のうち「他テスト・仕様から必要とされない」を14専用Pythonすべてが満たさない。専用test自体も現行Full Regressionの安全証拠であり、参照ゼロを作るためにtestを先に消すことはしない。追加削除は0件。PR #380で除去済みの13 Workflowを再導入しない。

## 未検証境界

import closureはAST importとリテラルmodule参照、Workflowのscript/module文字列を対象とする。動的に組み立てたimport名、外部運用手順、保存済みGitHub runからの手動実行は未証明。Production共通helper、budget/persistent counter、Reader Summary、Notion/note、Publication/Gate/Safetyは保持した。
