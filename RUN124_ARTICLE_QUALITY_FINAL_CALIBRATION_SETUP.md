# Run124 Article Quality Final Calibration — Setup

## 導入
1. Run124完成版を`main`へ反映する。
2. 新しいNotionプロパティ、Secrets、Variablesは追加しない。
3. 既存のRun123/Run120までの本番設定を維持する。
4. 任意で`Synthetic Regression Suite = full`を実行する。
5. Gemini API枠が利用可能なときに`Real Article Regression Test`を1回実行する。

## Real Article Regressionで確認する点
- MCP記事で`1リクエスト`がFalse Rejectされないこと。
- `WIMSE (Workload Identity in Multi-System Environments)`がSource BoundaryでFalse Rejectされないこと。
- Kobo/ESP32等でAI Editorial Registerが高密度に積み重なる場合、Human Appeal/AI-style reviewが働くこと。
- 単発の自然な評価語だけで過剰Reviewにならないこと。

## 追加コスト
- 追加Gemini call site: 0
- Notion schema migration: 不要
- 新規GitHub Secret/Variable: 不要
