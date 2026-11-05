# AIIF 正規 Daily Full 発火経路 — ChatOps 契約

状態: 正規運用仕様（PR #802 により main へ統合済み）。基準: main の実装を優先。ChatOps 発火の現在の E2E 成功は未検証。

## 正規ルート

ユーザーの「Dailyスタート」は、重複チェックを行ったうえで、GitHub Issue を介する ChatOps を第一候補とする。

1. 同一依頼の発火履歴・実行中 Daily を確認し、重複の疑いがあれば fail closed。既存 Run があればその Run を追跡する。
2. GitHub Issue を作成する。タイトルは `[AIIF RESERVED RUN]` で始め、ラベル `aiif-reserved-run` を付ける。Issue 本文には改行区切りで `mode=full`、`editorial_style=classic` を指定する。任意の `exact_target` と `excluded_models` は通常 Daily では空欄とする。
3. `.github/workflows/reserved-one-shot-trigger.yml` は Issue opened、author_association=OWNER、上記ラベルとタイトルの一致を要求する。GitHub API で Issue を作る主体が OWNER と判定されない場合、発火しない。ラベルは Issue 作成時に付与すること（後付けは opened イベントを再発火しない）。
4. 検証後、Workflow は GH_PAT を用い、`daily-one-shot.yml` を main 上で `mode=full`、`editorial_style=classic`、`confirm=RUN_ONCE` により dispatch する。成功時、Issue に記録して close する。
5. Run ID を特定し、Gemini routing・503/5xx・Ready件数・Quality/Human Appeal/Publication Gate・note下書き配送・Production write を確認して報告する。未確認の結果は成功とみなさない。

## 制限とフェイルセーフ

- ChatOps はユーザーの承認に基づく明示的な一回限りの発火であり、自動定期 Daily は再開しない。
- GitHub Issue 作成権限があっても OWNER 条件を満たすとは限らない。未検証なら試験的な Production 発火はしない。
- GitHub の workflow concurrency は同時実行の制御であり、依頼単位の厳密な重複排除ではない。Issue の重複作成を防ぎ、dispatch 結果が不明なら再作成しない。
- 発火後は二重 dispatch を行わない。認証エラーや GH_PAT 不備なら停止して報告する。
- 既存 `reserved-one-shot-trigger.yml` は Issue の再開・編集・ラベル追加では発火しない。
- `daily-one-shot.yml` の既定値は `classic`。変更する場合は明示的な指示を要する。
- ChatOps が不可能な場合はその理由を示し、手動 GitHub Actions を代替手段とする。迂回して無断で他の本番発火経路を試さない。

## 実装確認事項

この文書は現行 YAML を確認して記述したが、ChatGPT GitHub connector の Issue 作成者が OWNER と認識されるか、実際の ChatOps 発火が成功するかは未検証。これらを本番発火なしで確認してから、正規運用として有効化する。

参照: `.github/workflows/reserved-one-shot-trigger.yml`、`.github/workflows/daily-one-shot.yml`。
