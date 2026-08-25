# Run130 Fresh Article Regression Validation — 2026-08-25

## 実装確認
- `workflow_dispatch.inputs.article_set` に `fixed` / `fresh` を追加。
- `REGEN_TEST_ARTICLE_SET` の既定値は `fixed`。既存Workflowの意味を保持。
- `fresh` は source-native fetch → Legal Safety → Notion READ ONLY dedupe → 0-API metadata selection → Deep Dive/Quality Gate の順。
- Production write pathは使用しない。
- 新規Gemini call site 0。

## 反証テスト
- Run130専用 unittest: 6/6 PASS
- 全 unittest: 673/673 PASS
- pytest: 673 passed + 19 subtests PASS
- Synthetic Full: 500/500 PASS
- critical failures: 0
- production_write_isolation: true
- compileall: PASS
- GitHub workflow YAML: 8/8 PASS
- `_generate_via_chat(` call sites: 7（Run129から不変）
- `genai.Client(`: 1（Run129から不変）

## 反証した失敗条件
1. fixedを選んだのにfresh selectorが呼ばれる → テストで否定。
2. freshを選んだのに既存Notion記事を再利用する → known URL除外テストで否定。
3. Notion dedupe read失敗時に未知のまま生成を続ける → Fail-Closedテストで否定。
4. fresh候補が単一ソースだけに偏る → 複数ソース候補時のsource diversityテストで否定。
5. fresh追加でGemini call siteが増える → source count固定テストで否定。
6. Workflow UIにfresh選択肢が出ない → YAML内容テストで否定。

## Production E2E
Syntheticはローカルで500/500を確認済み。実際の新規記事品質・外部ソース取得・Gemini実生成についてはGitHub Actionsで `article_set=fresh` を1回実行し、Artifact実稿を人間監査して最終確認する。
