# Gemini Quota Safety Counter 設定

## 結論

`GEMINI_QUOTA_PROJECT_ID` は **任意設定** です。未設定・GitHub Actionsから取得できない場合でもDailyは停止しません。

このPipelineのPersistent CounterはGitHub repository内の `.runtime/gemini_daily_usage.json` に保存されるため、観測できるのは「このrepositoryから送ったGemini API試行」だけです。Google AI Studioの手動利用や別repositoryからの利用までは観測できません。

そのため、Counterの安定identityはrepository scopeに固定し、Google AI StudioのProject-wide RPD表示を最終的な正とします。

## GitHub Actionsの動作

Workflowは次の順でProject IDを任意取得します。

1. Repository Variable `GEMINI_QUOTA_PROJECT_ID`
2. 同名のRepository Secret
3. どちらも取得できなければ、`github.repository` をCounter scopeとして自動使用

Project IDが取得できなくても、次のWARNINGだけを出して処理を継続します。

```text
[GEMINI QUOTA PREFLIGHT] GEMINI_QUOTA_PROJECT_IDはWorkflowから取得できませんでした。Repository-local counterへ自動フォールバックします。
```

## Project IDを設定する場合

GitHub repository → Settings → Secrets and variables → Actions → Variables で任意設定できます。

- Name: `GEMINI_QUOTA_PROJECT_ID`
- Value: Gemini API keyが属するGoogle AI Studio / Google Cloud Project ID

値は監査用fingerprintとしてのみ使われ、生のProject IDはcounter stateやusage auditへ保存しません。

## 重要な制約

Persistent CounterはGoogle側Quota APIではありません。したがって、AI Studioや別のプログラムで同じProjectを使った分は自動反映できません。

無料枠管理では次の優先順位で確認してください。

1. **Google AI Studio Rate Limits画面**: Project全体の最終的な使用量
2. `gate_history/gemini_usage_*.json`: このPipeline Runが送った試行の詳細
3. `.runtime/gemini_daily_usage.json`: このrepositoryからの継続的なSafety Counter

## Usage Audit

Daily終了時にmodel / request kind / success-error / token usageを集計します。詳細はPrivate Artifactの `gate_history/gemini_usage_*.json` に保存されます。

Prompt本文、未公開記事本文、API key、生Project IDは保存しません。


## Pending Retry専用枠

`daily.yml`では`GEMINI_PENDING_RETRY_REQUEST_BUDGET=2`を設定しています。これは前日までのPending Retryが当日のFresh Deep Dive枠を消費し尽くすのを防ぐ上限です。API送信に進まなかった試行はこの枠を消費しません。通常は変更不要です。
