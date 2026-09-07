# AI Intelligence Factory — Run282 仕様追補

最終更新: 2026-09-08  
Baseline: **Run282 — Current-policy Ready Inventory Recovery**  
Production Source of Truth: **`main`**

## 1. 目的

Run281でPublication Contractを正しく厳格化した結果、歴史的に`記事状態=Ready`だった48件は、現行ポリシーでは`source_ready=0`となった。内訳は、旧Publication Contractによるstale 43件、現行公開Source Contract外5件である。

Run282の目的は、この48件を一括再生成することではない。無料API枠と運用コストを守りながら、**事業価値の高い既存Readyを1件ずつ、現行Publication ContractのQuality Gateを再通過させる**ことで、実公開検証に必要な最小在庫を回復する。

## 2. 回復対象

対象は次の条件をすべて満たす既存Notion行だけとする。

- `Content Status = Deep Dive`
- `Article Status = Ready`
- Sourceが現行公開契約の `GitHub / HackerNews / ArXiv / OfficialVendor` のいずれか
- 同じNotionページに、チェックアウト中の`publication_contract.is_current_ready_block()`を満たす原稿ブロックが存在しない
- GitHub案件は既存Legal Safety Gateを再通過する

ProductHunt、Unknown、その他のretired/unsupported sourceは回復対象外とし、推測変換しない。

## 3. 候補順位

新しいGemini評価は候補選定に使わない。既にNotionへ保存済みの事業・品質指標だけで次の順に比較する。

1. `記事価値`
2. `判断スコア`
3. `Screening Score`
4. `Analyzed At`
5. 安定tie-breakとして記事名

この順位は「新しいDecision Score」を生成するものではなく、回復コストを最も価値の高い既存在庫へ集中させるための0-model選択である。

## 4. Gemini / コスト上限

Run282の1回の実行では以下をHard Limitとする。

- 回復候補: **最大1件**
- Deep Dive / Quality Retry等を含むモデル要求予算: **最大4 request**
- Fresh acquisition: **0**
- Screening: **0**
- Product Review: **0**
- 新規Stock作成: **0**

通常Dailyおよび通常ONE-SHOTの予算を増やさない。Run282は独立した明示実行のみとする。

## 5. Persistence / Fail-Closed

回復は既存Notion Page IDを`generate_intelligence_report(..., persist_results=True)`へ渡し、同じページ上で行う。別ページを新規作成して逃げない。

`accepted`というメモリ上の戻り値だけでは回復成功とみなさない。書込み後に同一ページを再読し、少なくとも以下を確認する。

- `Article Status = Ready`
- 現行`Publication Contract`を満たすbyte-valid manuscript blockが存在する

GateがRejected / Review / Quality Failedへ落とした場合、controllerはReadyへ戻さない。Quality Gateとcanonical persistenceが最終Authorityである。

## 6. 実行経路

専用workflow:

- `.github/workflows/current-policy-ready-recovery.yml`
- `workflow_dispatch`のみ
- confirmation: `RECOVER_ONE_READY`
- Daily scheduleは変更しない

ChatOps control issue #71からは、repository ownerの完全一致コマンドのみ許可する。

`/aiif run current_policy_ready_recovery`

`run202_chatops_control.py`で再認証し、`GH_PAT`で専用workflowを1回だけdispatchする。

## 7. Note Ready / VM境界

Run282は回復直後に`note_ready_sync.py`を同じworkflow内で実行し、現行Publication Contract準拠のReadyがNote投稿DBへ反映されたことを確認できるようにする。

ただしRun282では以下を**実行しない**。

- `note-create-draft.yml` dispatch
- note.com browser / Playwright
- VM起動
- private draft作成
- public note公開

これは「在庫回復」と「noteへのDraft投入」を別の因果イベントとして観測するためである。Draft作成はCurrent-policy Readyの実在を確認した後、別の明示操作で行う。Public releaseは引き続きhuman-only。

## 8. Publication fingerprintとの関係

`current_policy_ready_recovery.py`は、どの既存在庫を再検証するかを決めるbounded operational controllerであり、記事本文・Quality Gate・Evidence判定・公開Source Contractそのものを定義しない。そのためPublication Contract fingerprintには含めず、Run280/281 recursive dependency guardで狭いnon-publication exemptionとして明示分類する。

一方、実際に生成される原稿bytesとReady判定は、既存のfingerprinted canonical pipeline / runtime layers / Publication Contractが所有する。

## 9. 初回Production成功条件

Run282初回実行は、次を満たして初めて成功と判断する。

1. 既存stale Readyから1件だけ選定される
2. Fresh acquisition / Screening / Product Reviewが0
3. Gemini要求が4 request以内
4. 同じNotionページへ書き戻される
5. 現行Publication ContractのReady blockを再読できる
6. Note Ready再照合で`source_ready >= 1`になる
7. Draft workflow / VM / browserが起動しない
8. Scheduled DailyはPAUSEDのまま

1回目がQuality Gateで落ちた場合は「システム失敗」ではなく、その候補が現行品質基準を満たさなかった実測結果として扱う。ただしworkflow上で回復成功とは表示しない。原因を監査してから、別候補または必要な局所修正を検討する。
