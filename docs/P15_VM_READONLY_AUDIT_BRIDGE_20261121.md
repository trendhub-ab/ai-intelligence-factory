# P1.5｜既存GCP note VMへの読み取り専用台帳監査ブリッジ（2026-11-21）

**Status:** Draft PR / offline review only. No merge or live invocation from this document.

事業正本: [AIIF Business North Star](../docs/AIIF_BUSINESS_NORTH_STAR.md)。旧V1は引き続き停止。AIIF Nextの正本監査モジュールは [Next P1.5](https://github.com/trendhub-ab/ai-intelligence-factory-next/blob/bbf7b49cc4eae1975d3dc838d560c12ccccc3a61/src/aiif_next/p15_local_ledger_readonly_audit.py)。

## 確認済みの既存運用経路

2026-11-18 [Run 44116978478](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/44116978478) と 2026-11-19 [Run 44453113993](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/44453113993) で、既存GCP OIDC/WIF認証・永続VM start・`aiif-note-cloud` runner・read-only inspect・VM stopが成功した。この経路はDesktop Commanderとは独立している。

現行の [v0.4 single note draft bridge](../.github/workflows/v04-single-note-draft-bridge.yml) は Issue #204に限定した例外であり、2台帳一般監査に流用したりcreate/recoverを再実行したりしない。

## 新設範囲

`.github/workflows/p15-persistent-note-ledger-audit.yml` は上記GCP vars/GH_PAT/OIDCを従来の**旧ホスト側**で使う、owner-only `workflow_dispatch`。`ref=main`、`github.actor=trendhub-ab`、1回目のRun、正確な確認文字列 `AUDIT_P15_PERSISTENT_NOTE_LEDGERS` を要求。手動のみでschedule/push/issue_commentによる起動はない。

1. 旧v0.4の実行中・キュー中を拒否し、**v0.4と同じGitHub concurrency group `note-draft-create-v2`**でVM lifecycle全体を排他にする。
2. 既存PATで**Nextの特定コミットSHA** `bbf7b49cc4eae1975d3dc838d560c12ccccc3a61` のソースだけをcheckoutし、sha一致とNextの無API擬似台帳テストを検証。失敗ならVMは起動しない。
3. GCP WIF認証。既に起動中のVMは「この監査の所有物」と見なさず停止・乗っ取りを拒否。TERMINATEDの場合に限り起動する。
4. 起動済みの`aiif-note-cloud`が**1台のみ**と確認できた場合、既存runner上で Python 3.11 により `~/.aiif-note/delivery-ledger-v1.sqlite3` と `~/.aiif-note/v04-private-drafts-v1.json` を読み取る。常に固定エラーコード/件数以外を外へ出さない。
5. この監査がVMを起動できた場合、正常終了・読み取りエラー・runner offlineなどの終了時に別のGCP jobでVMを停止する（クラウド障害、GitHubキャンセル等では停止保証なし。請求監視が必要）。

## 不変・未証明の区分

- 新規Notion/Note書込、Gemini/LLM、Chrome、Draft作成/再試行、Public公開、V1 Daily、記事のReady変更は**0**。
- Nextへ旧Production secretsを移送しない。既存GCP WIF・PATを旧ホスト側で使ってrunnerを立ち上げ、Nextの**監査コードのみ**をSHAで固定して呼び出す。
- ファイル・構造・ドラフトID衝突・曖昧状態の**監査**であり、lineage/Article ID/delivery_keyとのNotion総照合を完了しない。Ready承認・配送権限は常にfalse。
- live結果が`P15_STOP`でも台帳を直さず、人間判断まで停止。未作成ファイルを自動生成しない。
- GitHub CI GREENはホストと2台帳の存在や権限を立証しない。GCP VM課金額も未計測。現物のread-only runが別途必要。
- オーナーの`マージゴー`と、**その後の`実VM監査GO`は別承認**。Draft PR時点でいずれも実行しない。

## オフライン検証・運用

`python v1_retirement_contract_guard.py` は87→88 workflow構成のうち、旧V1 81本が停止し続けること、既存v0.4 2例外が変わらないこと、P1.5だけが新規の所有者限定監査例外であることを検証する。

`python -m unittest tests.test_run_p15_vm_audit_bridge -v` は起動条件、排他、固定SHA、read-only、停止jobなどを検証し、existing Integration Reconciliation CIで必ず実行する。実VMではNext P1.5の独立テスト10件もstart前に走らせる。

**安全なライブ試験のチェック:** 事前にmain SHA・必要CI・既存v0.4 runがいないこと・VMが停止中であること・利用するPAT/WIFが有効であることを確認。ワークフロー入力は`confirm=AUDIT_P15_PERSISTENT_NOTE_LEDGERS`のみ。run後、両台帳のaggregate結果とVM停止成功を確認。Note/Notion/Productionへの操作は承認しない。
