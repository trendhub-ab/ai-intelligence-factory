# Gemini Quota Safety Counter 設定

最終更新: 2026-09-03  
現行Quota Safety Baseline: **Run209 — timeout RPD fail-closed**

## 結論

`GEMINI_QUOTA_PROJECT_ID` は **任意設定** です。未設定でもrepository-local counterへフォールバックできます。

ただし、Persistent CounterはGoogle側Quota APIではありません。観測できるのは原則として「このrepositoryから送ったGemini API試行」です。Google AI Studioの手動利用や別repositoryからの利用までは自動観測できません。

したがって、無料枠管理では **Google AI Studio Rate LimitsのProject-wide表示を最終的な外部実態** とし、Factory counterは安全弁として使います。

## 1. Flash系の安全上限

現行ONE-SHOT Productionでは以下を安全上限として維持します。

- `gemini-3.6-flash`: **18 requests/day**
- `gemini-3.7-flash`: **18 requests/day**
- `gemini-3.5-flash`: **18 requests/day**

AI Studio側で20 RPDが表示されている場合でも、Factoryは**18/20で停止**し、残り2回を安全余白として残します。

この18回上限は「もっとAPIを使うため」の値ではなく、provider実態との差・手動利用・通信不確実性を吸収するための安全弁です。20まで引き上げて使い切ることを前提にしません。

Flash Lite等の別モデルはworkflowに設定された各daily budgetを正とします。値を推測せず、`.github/workflows/daily-one-shot.yml`の現行値を確認してください。

## 2. Run209 — timeout時のRPDはFail-Closed

Google AI Studioの実測により、transport timeout / watchdog timeoutでクライアントが応答を観測できなくてもprovider側RPDが消費される場合が確認されました。

そのためRun209以降のProductionでは、Gemini送信前に予約したPersistent RPDを**timeoutだからといって巻き戻しません**。

- timeoutは「未消費」と楽観判定しない。
- `release_unobserved`をProduction RPD残量を増やす目的には使わない。
- 既存stateに過去の`released_unobserved`履歴が残っていても監査情報として扱う。
- 新しいtimeoutは1 request消費したものとして安全側に保持する。
- 18回安全上限はそのまま維持する。

実装は`gemini_timeout_rpd_fail_closed.py`を`run203_runtime_state_channel.py`の後、`gemini_transient_recovery.py`の前にinstallします。

## 3. Project ID / Counter scope

Workflowは次の順でProject IDを任意取得します。

1. Repository Variable `GEMINI_QUOTA_PROJECT_ID`
2. 同名のRepository Secret
3. どちらも取得できなければ`github.repository`をCounter scopeとして使用

Project IDが取得できなくても、生のProject IDをstateへ保存する必要はありません。値は監査用fingerprintとして扱います。

## 4. Runtime state channel

Persistent Counterは`.runtime/gemini_daily_usage.json`に継続保存されます。

Run203のruntime-state contractにより、ProductionではGemini reservation前にstate channelのwritability / continuityを確認します。stateを書けない状態で「後で直る」と楽観的にAPIを消費しないことが原則です。

`.runtime/`は生成ゴミではなくProduction continuity dataです。通常cleanupで削除・初期化してはいけません。

## 5. 使用量確認の優先順位

無料枠管理では次の順で判断します。

1. **Google AI Studio Rate Limits** — Project全体の最終外部実態
2. `gate_history/gemini_usage_*.json` — このPipeline Runが送った試行・結果
3. `.runtime/gemini_daily_usage.json` — repository-local Safety Counter

Factory counterとAI Studioが異なる場合、**AI Studioの使用量が多い側を安全上の正**として扱います。差異を理由に安全余白を削らないでください。

## 6. Pending Retry専用枠 — Run206 / Run207 / Run208

通常Production側にはPending Retry用の独立budgetがあり、Fresh Deep Dive枠の無制限消費を防ぎます。

一方、`pending_retry_validation.py`のfast laneではRun207により、process import前に専用budgetを**最大3 requests**へ固定します。目的は、次の最悪ケースでも品質修復1回を残すことです。

`provider failure → valid generation → one quality recompose`

fast lane固有契約:

- 最大3 requests。
- 1回目のHTTP 503でそのmodelを当該fast-lane run中cooldown。
- 1記事成功で停止。
- fresh collection / screeningは行わない。
- Run208のReader Value repairは最大1回、Reader-only failureに限定。
- Fact/Evidence/Publication gateは緩和しない。

通常ProductionのRun205 transient-recovery policyやglobal daily counterは変更しません。

## 7. Usage Audit

Run終了時にmodel / request kind / success-error / token usageを集計し、Private Artifactの`gate_history/gemini_usage_*.json`へ保存します。

保存しないもの:

- Prompt本文
- 未公開記事本文
- API key
- 生Project ID

## 8. Daily / ONE-SHOT運用

- Scheduled Dailyは現在 **PAUSED**。
- Production API実行は明示的なONE-SHOTを基本とする。
- Daily PAUSED stubの環境変数をProduction完全設定として推測しない。
- 実際のProduction quota値は`daily-one-shot.yml`と実行コードを優先する。
- quota確認・回帰検証のためだけにGemini APIを消費しない。可能な検証はzero-API testで行う。

## 9. Documentation Freshness

Quota安全仕様を変更する場合は、コード/workflowと同じPRで本ファイルを更新します。Run210 Documentation Freshness Guardにより、Flash 18回安全上限、Daily PAUSED、timeout fail-closed、Pending Retry fast lane等のCanonical契約が実装と矛盾した場合はCIを失敗させます。
