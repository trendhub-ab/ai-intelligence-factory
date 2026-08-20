# Gemini Quota Project Scope Setup

この修正版ではGeminiの永続Safety CounterをAPIキー単位ではなくGoogle Project単位で管理します。

## 必須設定

GitHub Repositoryの **Settings → Secrets and variables → Actions → Variables** に次を追加してください。

- Name: `GEMINI_QUOTA_PROJECT_ID`
- Value: Gemini APIキーが所属しているGoogle AI Studio / Google CloudのProject ID

`GEMINI_PERSISTENT_DAILY_COUNTER=true`のままこの値が未設定の場合、PipelineはGeminiを1回も呼ぶ前にFail-Closed停止します。

## なぜ必要か

同一Google Project内でAPIキーを交換・追加してもGeminiのRPD/RPM quotaは共有されます。旧実装のAPI-key hash単位counterでは、キー交換時に内部使用量が0へ見える可能性がありました。

新実装ではProject IDの生値を保存せず、SHA-256短縮scopeだけを`.runtime/gemini_daily_usage.json`へ保存します。旧`key_scopes`形式が当日分に残っている場合は、使用量を新Project scopeへ保守的に合算して移行します。

## 実行後の確認

Daily log / Telegramに以下のような内訳が出ます。

```text
Gemini API Attempts: 17 (success=16, error=1) tokens(prompt=18220, output=1720, total=19940)
Models: gemini-3.5-flash-lite=11 (...screening_batch/global_calibration...) | gemini-3.6-flash=6 (...deep_dive/quality_retry...)
```

詳細はPrivate Artifactの`gate_history/gemini_usage_*.json`に保存されます。Prompt本文・未公開記事本文・APIキー・生Project IDは保存しません。
