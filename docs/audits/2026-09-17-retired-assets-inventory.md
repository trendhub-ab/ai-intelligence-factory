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


## 2026-09-18 Run290〜299残存branch監査

現行main `1dec755054b453e51d8c7ff92c43ff911c99ab77` を基準に、`run29*` の残存branch 19本をGitHub上で比較した。全branchはmainより500件以上behindしており、現在の運用branchではない。対応PRのmerge状態と現在のbranch HEADを照合し、merge後にbranchだけで進んだcommitの有無も確認した。

### 削除可能と判定したbranch

以下17本は、対応する変更がmainへmerge済み、または後続のmerge済み修復へ吸収済みであり、現行運用の唯一の参照元ではない。

- `run290-separate-quality-revocation-from-human-posting` — PR #174 merge済み。branch HEADはmerge時headと一致。
- `run291-private-draft-readonly-audit` — PR #175 merge済み。branch HEADはmerge時headと一致。
- `run291-1-private-draft-audit-chatops` — PR #176 merge済み。固定ChatOps入口はPR #387で退役済み。
- `run292-note-rendered-body-audit` — PR #177 merge済み。
- `run293-private-draft-guard-diagnostics` — PR #178 merge済み。
- `run294-eyecatch-persistence-diagnostics` — PR #179 merge済み。
- `run295-shared-eyecatch-persistence-proof` — PR #180 merge済み。
- `run296-editorial-format-v2` — PR #181 merge済み。
- `run297-298-genrec-refresh` — PR #182 merge済み。
- `run297-298-workflow-yaml-fix` — PR #183 merge済み。
- `run297-asset-branch-fix` — PR #184 merge済み。
- `run298-skip-unreadable-history` — PR #185 merge済み。
- `run298-existing-header-replace` — PR #186 merge済み。
- `run298-header-readonly-diagnostics` — PR #187 merge済み。
- `run298-header-diagnostic-trigger-fix` — PR #188 merge済み。
- `run298-hover-header-final` — PR #189 merge後に「note mutation前に1280×670を厳密確認する」1 commitがbranchへ追加されたが、このone-off経路は後続Run300修復へ置換され、現行mainでは当時のone-off Workflow自体が退役済み。現行機能の唯一の実装ではない。
- `run299-genrec-body-structure-diagnostic` — PR #191 merge済み。

これらの削除はGit履歴・merge済みPRの記録を消すものではない。GitHub connectorにはbranch delete actionがないため、この監査ではref削除そのものは実施していない。

### 保持するbranch

以下2本は現時点では削除しない。

- `run297-assets` — reviewed GenRec eyecatch画像2点を保持するasset branch。過去のNotion/外部raw URL参照がbranch名に依存している可能性を否定できないため、参照切れの実証なしに削除しない。
- `run298-body-repair-final` — PR #190は2026-09-18にsupersededとしてcloseしたが未merge。後続Run300で修復方針は置換済みとはいえ、このbranchはPR #190の未統合実装そのものを保持するため、履歴保全目的で残す。

### 削除前提ではないもの

branch refの整理と、mainに残るRun297〜302 helper/testの削除可否は別問題である。main側のhelper/testは本監査文書冒頭のとおり、現行テスト・後続helperから参照されるものがあり、branch削除を理由に削除しない。


## 2026-09-18 Run300〜399 / legacy branch監査

現行main `612bf0d7dcd93e1edaa37d52ab5ad799346b0ee6` を基準に、Run300〜399系111 branchと、旧Groq/X/cleanup/audit系branchをGitHub PR履歴・現在HEAD・後続superseding PRで照合した。

### Run300〜399

111 branchのうち107本を削除候補、4本を保持と判定した。

削除候補の基本条件:
- branchに対応する最新PRがmerge済みで、現在branch HEADがそのPR HEADと一致する。
- または、未merge/PRなしでも後続の正式merge済みPRが同一機能を置換し、main側に主要実装が残ることを確認できる。

特記事項:
- `run308-public-copy-alignment`: PR #205は未mergeだが、同目的を2 docsだけで再構成したPR #206がmerge済み。削除候補。
- `run315-exact-body-replace-fix`: PRなし。主要Python `run315_member_onboarding_update.py` はmainとbyte-identical。Workflow/Testはmain側が後続修正済み。削除候補。
- `run317-onboarding-server-save`: PRなし。主要Python/Workflow/Testはmainとbyte-identical。正式なPR #225もmerge済み。削除候補。
- `run328-profile-settings-probe`: PR #241は未mergeだが、PR #242が「#241と同一挙動をcurrent mainから再作成したsuperseding PR」と明記してmerge済み。削除候補。
- `dev/run361-result-contract`: branchはPR #288後も進んだが、最新HEADはPR #289としてmerge済み。削除候補。

保持:
- `backup/gemini-only-run359-20260912`
- `backup/gemini-run356-966a0f1`
- `backup/gemini-only-run360-20260912`
- `fix/run367-readonly-audit-reader-conflict` — PR #304は未mergeのまま2026-09-18にsupersededとしてclose。53 files / 135 commitsの独自監査・実装を持つため、branch refは履歴保全目的で残す。

したがって、上記4本を除くRun300〜399監査対象branchは削除候補である。branch削除はGitHub connectorにdelete-ref actionがないため、この監査では実行していない。

### 旧Groq branch

現行mainで `GROQ_API_KEY`, `groq_provider`, `groq.com`, `gpt-oss` の実装参照は検出されず、PR #305でGemini-only Productionへ復帰済み。

削除候補:
- `dev/groq-provider-foundation` — PR #281は未mergeでclose済み。PR diffに履歴が残る。

保持:
- `dev/hybrid-groq-gemini`
- `runtime/groq-validation`
- `safety/groq-screening-shadow-falsification`
- `validation/groq-screening-ab-run46`

上記4本はPRなしの独自実験branchであり、branch refを消すと唯一の履歴を失う可能性を否定できないため保持する。現行Productionへ戻す候補ではない。

### 旧X branch

現行Xは後続のPR #365〜#367でmain側の正式Daily/ChatOps経路へ統合済み。

削除候補:
- `chore/x-candidate-watchlist-50` — PR #268 close済み。
- `feature/x-bounded-factory-validation` — PR #269 close済み。
- `feat/chatops-x-stage2-zero-gemini-20260915` — PR #366 merge済み。
- `feat/x-daily-full-integration-20260915` — PR #367 merge済み。
- `fix/x-workflow-main-hygiene-20260914` — PR #347 merge済み。
- `test/x-daily-bridge-zero-gemini-20260915` — PR #365 merge済み。

保持:
- `backup/main-before-x-integration` — X統合前のrollback anchor。
- `feature/x-discovery-ingestion` — PRなしの旧base branch。
- `feature/x-intelligence-layer` — PRなしの旧base branch。

PRなし2本は現行mainの実行元ではないが、独自基礎履歴の唯一性を否定できないため保持する。

### merged cleanup / audit branch

以下は対応する最新PRがmerge済みで現在HEADも最新PR HEADと一致するため削除候補。

- `cleanup/gemini-only-repository` — PR #305
- `cleanup/remove-run366-one-shot-bridge` — PR #303
- `cleanup/retire-fixed-note-audit-chatops-20260918` — PR #387
- `cleanup/semantic-guards-20260913` — PR #308
- `audit/member-access-correction-20260918` — PR #383
- `audit/pending-retry-36-expiry-20260918` — PR #385
- `audit/provider-budget-isolation-20260918` — PR #384
- `audit/repository-contracts-20260917` — 同一branchをPR #380〜#382で再利用し、現在HEADは最新PR #382 HEADと一致
- `audit/run362-ready-provenance` — PR #298

### 重要な区別

branch refの削除候補判定は、main内のhelper/test/file削除可否とは独立している。branchを削除しても、現行Full Regressionや後続helperから参照されるmainファイルは削除しない。rollback/独自実験の唯一性を否定できないbranchは、現行Productionで使わなくても保持する。

## 2026-09-18 Run400〜425残存branch監査

現行main `e8d83ff854f9346fc5a414a1bcd24ecaa25226d4` へ再照合し、Run400〜425系31 branchをGitHub上のPR履歴・現在HEAD・mainとの祖先関係で照合した。

### 削除候補: 29本

以下は、対応する最新PRがmerge済みでbranch HEADがそのPR HEADと一致するか、PRなしでもbranch tipが現在mainの祖先で独自未統合commitを持たないため、branch ref削除候補と判定した。

- `fix/run400-approved-reader-repair`
- `fix/run401-approved-budget-headroom`
- `fix/run402-exact-approved-target`
- `fix/run403-pending-target-source`
- `fix/run404-combined-quality-repair`
- `fix/run405-reader-density-compression`
- `fix/run405-reader-repair-specificity`
- `fix/run406-approved-second-reader-repair`
- `fix/run407-approved-quality-fallback` — PRなしだがbranch tipは現在mainの祖先。後続PR #323/#324で正式経路がmerge済み。
- `fix/run408-approved-quality-fallback`
- `fix/run409-reader-repair-ownership`
- `fix/run410-approved-page-id-fallback` — PRなしだがbranch tipはPR #326 merge commitと一致し、現在mainの祖先。
- `fix/run410-quality-failed-exact-target`
- `fix/run411-fact-retry-specificity`
- `fix/run412-approved-38-35-routing`
- `fix/run413-oneoff-rubygems-manual-ready`
- `fix/run414-rubygems-eyecatch`
- `fix/run415-rubygems-eyecatch-parser`
- `fix/run416-zero-model-eyecatch-fallback`
- `fix/run417-note-body-verification`
- `fix/run418-japanese-eyecatch-font`
- `fix/run418-quota-auth`
- `fix/run419-eyecatch-plan-repair`
- `fix/run420-job-level-gemini-lock`
- `fix/run421-zero-model-canonical-layout`
- `fix/run422-pinned-source-bounded-copy`
- `fix/run423-preserve-latin-tokens`
- `fix/run424-current-canonical-replace`
- `hotfix/run425-editor-readiness`

### 保持: 2本

- `fix/run413-manual-zero-api-rescue` — mainとdivergeし、`.github/workflows/run413-manual-zero-api-rescue.yml`、`run413_manual_zero_api_rescue.py`、専用testの3独自資産を持つ。後続の正式Run413はPR #329で別branchからmerge済みだが、このbranch自体は未merge実験履歴の唯一性を否定できないため保持する。
- `fix/run425-required-intro-summary` — mainとdivergeし、Publication Contract試作変更、`run425_required_intro_summary.py`、`run425_rubygems_intro_restore.py`、専用testを含む6 commitの独自履歴を持つ。現行Run425はPR #342〜#344の別実装でmerge済みだが、このbranch refは未merge試作の履歴保全として保持する。

### 運用判断

上記保持2本は現行Productionの実行元ではない。再利用・merge候補として扱わず、履歴参照専用とする。削除候補29本についても、branch refを削除してもmerge済みPR/commit履歴は保持される。

GitHub connectorにはdelete-ref actionがないため、この監査ではbranch削除そのものは実施していない。
