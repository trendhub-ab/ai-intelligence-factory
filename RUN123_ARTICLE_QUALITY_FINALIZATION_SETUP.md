# Run123 Article Quality Finalization — Setup

## 目的
Run122後のReal Article Regressionで残った3点だけを、追加Gemini APIなしで修正する。

## GitHub / Notion設定
- 新しいGitHub Secret: なし
- 新しいRepository Variable: なし
- Notion DB / Property追加: なし
- 既存Run122/Run120までの設定をそのまま維持する。

## 導入手順
1. Run123完成版を`main`へ反映する。
2. GitHub Actions → `Synthetic Regression Suite` → branch `main` → `full`を実行する。
3. 500/500、critical=0、production_write_isolation=trueを確認する。
4. Gemini quotaが利用可能な時点で`Real Article Regression Test`を1回実行する。
5. Artifact `regression-test-output`を確認する。
6. Kobo: 裸のセクション名がMarkdown見出しとして修復され、構造誤Rejectが解消されるか確認する。
7. MCP: `5分野`が`unsupported numeric claim: 5分`にならないことを確認する。
8. ESP32: Editorial Register過密が再生成時に減るか、残る場合はHuman Appeal REVIEWへ送られることを確認する。
9. Real Article E2Eを監査後、通常Dailyへ進む。

## 重要
3/3 Acceptedを機械的な成功条件にしない。事実・Evidence不足が実際にある場合のRejectは正しい。成功条件はFalse Rejectが消え、Accepted記事のAI臭が十分抑制され、Hard Gateが維持されること。
