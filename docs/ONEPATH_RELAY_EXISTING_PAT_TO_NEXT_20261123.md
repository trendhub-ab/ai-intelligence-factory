# OnePath｜既存旧GH_PATをNextへ安全に引き継ぐワンショット経路

## 目的と現在地
PC接続や新PATの発行を必須としない。旧AIIFのowner-only Actionsで実在が確認されたGH_PATを、GitHubの標準Secret暗号化APIでprivate Nextへ配置できるようにする。旧AIIF [Run #45187982493](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/45187982493)では、現在の旧PATでNextのprivate repo・Next Secrets一覧/登録用公開鍵のGETが成功。**Secretsを書き込めるかどうかは未確認**。

## 重要な権限変更
既存の旧GH_PATを**別リポジトリNextのActions Secretとして利用可能にする**操作となる。新PATは作らないが、PATの実効的な露出範囲が増えるためリスクがある。NextのWorkflowにPATへのアクセス権が増えることを前提に、利用前にActionsのトリガー・ブランチ保護・PATスコープを確認する。

## 安全な実行経路
1. 本PRでワークフロー・テスト・V1停止ガードの厳密な例外をマージする。マージしただけでは実行されない。
2. **別途所有者が明示的にGOを出した場合のみ**、旧repoにOwner Issueを作る（Title: `AIIF OLD: APPROVE ONEPATH RELAY EXISTING PAT TO NEXT`、Body: `OWNER_APPROVES_ENCRYPTED_EXISTING_GH_PAT_RELAY_V1`）。owner/Issue author/main/run attemptを二重確認する。
3. まずNext Actions Secret `GH_PAT` のメタデータGETで不在を確認。既存なら停止・上書きしない。403や不明なレスポンスも停止する。
4. Next側のGitHub公開鍵を取得し、OLD側GH_PATの文字列をNaCl sealed boxで暗号化してNext `GH_PAT` Secretへ**1回だけ** PUT。外部リトライは禁止。
5. Next Secretの存在を読み戻して確認。途中失敗後の自動再試行は禁止。PAT・平文・暗号文・API本文はIssue、コード、Actionsログに表示しない。

## 事業・費用・互換性
既存旧GH_PATとNext/旧repoのSecrets基盤を再利用するため追加課金なし。既存のOnePath Ed25519/X25519ブートストラップPR #221/#222、記事/Notion/note/VM台帳は変更しない。旧V1の81運用ジョブは引き続き無効で、許可される例外はこの1ワークフローのみ。PAT移植後の鍵発行・非公開1件E2E・定時ONは独立した承認事項。

## 注意
GitHub Secretは後から平文を取得できない。Nextで存在確認できてもPATの書込権限や記事配送権限は別途実証する必要がある。古いPATに過大な権限がある場合は、将来最小権限のGitHub App/トークンに切り替えることを推奨。

追跡Issue：https://github.com/trendhub-ab/ai-intelligence-factory-next/issues/217