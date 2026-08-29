# Run128 Non-Engineer Accessibility Bridge Validation — 2026-08-25

## 狙い
Run127実稿で確認された「論理は通るが、非エンジニアには少し難しい」を局所的に解消する。

## 反証観点
1. 恋愛など特定の比喩を毎回強制し、記事がテンプレ化していないか。
2. 比喩のために技術的正確さ・Evidence・制約が落ちていないか。
3. 平易化がFact/Evidence/DecisionのHARD Gateを迂回していないか。
4. 新しいGemini API呼び出しを増やしていないか。
5. 高専門語密度なのに翻訳層がない記事を0-APIで観測できるか。

## 専用テスト
`tests/test_run128_non_engineer_accessibility_bridge.py`
- 非エンジニア向けpromptルール
- jargon-heavy / no-bridgeのsoft REVIEW
- 日常ブリッジ + 正式名称保持
- 恋愛は許可するが必須ではない
- HARD Gate非接続
- Article Audit新項目
- Gemini call site不変

## Local Validation Results
- Dedicated Run128: 7/7 PASS
- unittest discover: 661/661 PASS
- pytest: 661 passed + 19 subtests PASS
- compileall: PASS
- workflow YAML parse: 8/8 PASS
- `_generate_via_chat(` call sites: 7 (Run127と同数)
- `genai.Client(`: 1 (Run127と同数)
- Notion property追加: 0
- Synthetic Full: ローカル環境に `google.genai` が存在しないため起動前ImportError。これはRepositoryコードのテスト失敗ではなく依存環境不足。GitHub Actionsはrequirementsをinstallするため、release branchでFullを実行して最終確認する。

## Release判定
Local unit/pytest上はPASS。Production投入前にGitHub Actions `Synthetic Regression Suite / full` を実行し、500/500・critical 0・production write isolationを確認する。Geminiを使うReal Article Regressionは、その後に3本だけ実施して日常翻訳の実稿品質を人間監査する。
