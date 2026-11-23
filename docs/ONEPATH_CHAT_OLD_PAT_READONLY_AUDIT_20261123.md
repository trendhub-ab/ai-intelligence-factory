# OnePath｜既存の旧AIIF認証を利用したChat完結ルートの読取専用調査

## 決定された目的
所有者PCでの秘密鍵発行・PAT生成を必須とせず、Chat → GitHubオーナーIssue → 既存Actions → 既存クラウドVMでAIIF Nextの非公開下書きE2Eへ進む。新規有料サービスは導入しない。一般公開は禁止。

## 事実と不確実性
- Next mainのRun [#45185606472](https://github.com/trendhub-ab/ai-intelligence-factory-next/actions/runs/45185606472)ではNext側`GH_PAT`と`AIIF_NEXT_PUBLIC_JWK_JSON`の未設定が判明した。Gemini、Quota、Fernetは設定済み。
- 旧repoの既存ワークフロー`v04-owner-chatops-inspect.yml`は`secrets.GH_PAT`を参照し、[Run #44453098459](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/44453098459)（11月19日）でその存在検査とdispatchが成功していた。**現在の秘密鍵状態・期限・Next管理権限は未確認**。
- GitHub標準の`GITHUB_TOKEN`はリポジトリやWorkflowごとに発行される。異なるrepoへのSecrets/Variables管理権限があると推定しない。GitHubのREST APIでActions Variables/Secretsを設定するには必要なトークン権限が別途必要。

## このPR：read-onlyの権限調査のみ
旧repoのmainに新ワークフロー`.github/workflows/onepath-old-pat-chat-readonly-audit.yml`を追加する。

マージ後、Chatから所有者`trendhub-ab`として**正確な**Issueを開く。
- Title：`AIIF OLD: READ-ONLY ONEPATH EXISTING PAT AUDIT`
- Body：`VERIFY_OLD_GH_PAT_METADATA_ONLY_NO_WRITES`

owner・Issue作成者・public repo・main・初回attemptを検証。Runには次の結果だけを表示する。
- 旧repoで`GH_PAT`、Notion/Note認証、旧X25519秘密鍵、GCP VM/WIF関連設定が存在するかの真偽。
- 旧repoの`GH_PAT`でNextのprivate repo、Next/旧のVariables/Secrets一覧や登録用公開鍵のエンドポイントが**GETだけでアクセス可能か**の真偽。レスポンス、秘密値、トークン、キーIDを一切ログ表示しない。

### 停止条件
- 旧repo GH_PATが未設定または失効していれば、PCなしの既存PAT再利用はそのままでは不可とする。
- PATでGETが成功してもSecrets/Variablesの書込み権限の証明とはしない。**このPRでは書込権限確認のためのPOST/PUTもしない**。
- 現行NextのOnePath公開/署名/暗号ポリシー、旧レポジトリの既存ProductionやVMは変更しない。Gemini、Notion、noteにも触れない。

## 調査が合格した場合の別段階
旧repoの既存owner PATを再利用したOnePath鍵構成を最小権限で提案する。ただし秘密の文字列をChat・Issue・PR・コミットにコピーしない。権限と設計が揃った場合のみ、所有者の別途明示承認と独立した実行ガードの下で設定を進める。初回非公開1件E2Eおよび定時ONはさらに別の承認とする。

## 参照
- E2E統合台帳: https://github.com/trendhub-ab/ai-intelligence-factory-next/issues/217
- Nextの署名・暗号ブートストラップ: PR #219、#221、#222（すべてマージ済み）
