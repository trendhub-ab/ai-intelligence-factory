# Gemini Quota Safety Counter 設定

最終更新: 2026-09-09  
現行Quota Safety Baseline: **Run209 — timeout RPD fail-closed**  
現行Provider Resilience Baseline: **Run303 — verified 503 confirmation / consecutive-only circuit**  
現行Article Model Routing Baseline: **Run261 — Run260 Live-Path Hardening / Gemini 3.7 Primary / 3.8 Quality Rescue**

## 結論

`GEMINI_QUOTA_PROJECT_ID` は **任意設定** です。未設定でもrepository-local counterへフォールバックできます。

ただし、Persistent CounterはGoogle側Quota APIではありません。観測できるのは原則として「このrepositoryから送ったGemini API試行」です。Google AI Studioの手動利用や別repositoryからの利用までは自動観測できません。

したがって、無料枠管理では **Google AI Studio Rate LimitsのProject-wide表示を最終的な外部実態** とし、Factory counterは安全弁として使います。

## 1. Flash系の安全上限

現行ONE-SHOT Productionでは以下を安全上限として維持します。

- `gemini-3.8-flash`: **18 requests/day**（Run260で追加。`GEMINI_38_FLASH_DAILY_BUDGET`は18以下へ下げる用途のみ）
- `gemini-3.7-flash`: **18 requests/day**
- `gemini-3.6-flash`: **18 requests/day**
- `gemini-3.5-flash`: **18 requests/day**

Google公式では2026-09-02時点で`gemini-3.8-flash`はGA/StableかつGemini API Free TierがFree of chargeです。ただし、Google側の実効rate limitはProject/TierのAI Studio表示を正とし、本ファイルの18回はGoogleの普遍的なquota値を主張するものではありません。

AI Studio側で20 RPDが表示されている場合でも、Factoryは**18/20で停止**し、残り2回を安全余白として残します。3.8についてAI Studio側の実効上限が18未満に表示された場合は、`GEMINI_38_FLASH_DAILY_BUDGET`をその値よりさらに安全側へ下げます。

この18回上限は「もっとAPIを使うため」の値ではなく、provider実態との差・手動利用・通信不確実性を吸収するための安全弁です。20まで引き上げて使い切ることを前提にしません。

Flash Lite等の別モデルはworkflowに設定された各daily budgetを正とします。値を推測せず、`.github/workflows/daily-one-shot.yml`の現行値を確認してください。

### Run261 Article Model Routing

記事側Productionのモデル優先順位は次のとおりです。

- Fresh Deep Dive: `gemini-3.7-flash -> gemini-3.8-flash -> gemini-3.6-flash -> gemini-3.5-flash`
- 既存のmodel-based `quality_retry`: `gemini-3.8-flash -> gemini-3.6-flash -> gemini-3.5-flash -> gemini-3.7-flash`
- Screening: 既存Flash-Lite poolを変更しない。
- deterministic rescue: 既存zero-API経路を変更せず、不要な3.8 callへ置換しない。

Run260は既存の`_call_model_pool`を並べ替えるrouting layerとして導入しました。Run261はONE-SHOT #28の実測で、Productionが`_call_deep_dive_pool`を経由する際にquality retryの先頭が3.7になり得ることを確認したため、実Production入口にも同じquality-first契約を追加しました。Run261のlive-path wrapperは既存`_call_model_pool`へ**1回だけ**委譲し、新しいretry loopやprovider call pathを追加しません。

`.github/workflows/daily-one-shot.yml`のProduction/Pending Retry環境もRun261でcanonical poolを明示します。Deep Dive全体の1-run上限12、Pending Retry budget、503 cooldown、各Gateは従来どおりです。別系統のProduct Review routingは意図的に変更しません。

## 2. Run209 — timeout時のRPDはFail-Closed

Google AI Studioの実測により、transport timeout / watchdog timeoutでクライアントが応答を観測できなくてもprovider側RPDが消費される場合が確認されました。

そのためRun209以降のProductionでは、Gemini送信前に予約したPersistent RPDを**timeoutだからといって巻き戻しません**。

- timeoutは「未消費」と楽観判定しない。
- `release_unobserved`をProduction RPD残量を増やす目的には使わない。
- 既存stateに過去の`released_unobserved`履歴が残っていても監査情報として扱う。
- 新しいtimeoutは1 request消費したものとして安全側に保持する。
- 18回安全上限はそのまま維持する。

実装は`gemini_timeout_rpd_fail_closed.py`を`run203_runtime_state_channel.py`の後、`gemini_transient_recovery.py`の前にinstallします。Run260/261のrouting layerはその後にinstallし、既存のquota/timeout recoveryを迂回しません。


## 2.1 Run303 — provider HTTP 503の確認再試行

Run35/Run36の実Production反復で、SDK下の実HTTP 503と、同一modelの後続HTTP 200成功が同じrun内に共存することを確認しました。したがってRun303では、一時的な503を即座にrun-wide model failureへ昇格させません。

- HTTP 503は例外本文の文字列ではなく、構造化されたnumeric provider status code=503でのみ認定します。
- 1回目のverified 503では同一modelを1回だけ確認再試行します。既定待機10秒、上限20秒で、providerのretry delayが得られる場合はその範囲で尊重します。
- 2回連続のverified 503で初めてrun-local circuitを開きます。
- 200成功、timeout、429、404、その他non-503結果で503系列をリセットします。成功を挟んだ過去503を累積してcooldownしません。
- transport timeoutは503とは別障害です。Run209のtimeout reservation fail-closed契約は変更しません。
- 確認再試行は既存Deep Dive 12 requests、Pending Retry、Product Review、各model persistent daily safety capの内側でのみ動作します。
- Fact / Evidence / Publication / Human Appeal Gateは変更しません。Ready件数を増やす目的でGateを緩和しません。

実装正本は `gemini_provider_resilience.py`、詳細反証は `docs/reference/RUN303_GEMINI_PROVIDER_503_RESILIENCE.md` です。

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

## 6. Pending Retry専用枠 — Run206 / Run207 / Run208 / Run261

通常Production側にはPending Retry用の独立budgetがあり、Fresh Deep Dive枠の無制限消費を防ぎます。

一方、`pending_retry_validation.py`のfast laneではRun207により、process import前に専用budgetを**最大3 requests**へ固定します。目的は、次の最悪ケースでも品質修復1回を残すことです。

`provider failure → valid generation → one quality recompose`

fast lane固有契約:

- 最大3 requests。
- 1回目のverified HTTP 503は同一modelで1回だけ確認再試行し、単発503ではcooldownしない。
- 2回連続のverified HTTP 503で当該modelのrun-local circuitを開く。
- 1記事成功で停止。
- fresh collection / screeningは行わない。
- Run208のReader Value repairは最大1回、Reader-only failureに限定。
- Run261によりmodel-based quality repairは実Production入口でも3.8を先頭にするが、request上限は増やさない。
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
- 実際のProduction quota値は`daily-one-shot.yml`、Run260/261 runtime routing、および実行コードを優先する。
- ONE-SHOT成功後の直接fan-outはRun261以降、受動`workflow_run`ではなくONE-SHOTから`GH_PAT`で明示dispatchする。
- quota確認・回帰検証のためだけにGemini APIを消費しない。可能な検証はzero-API testで行う。

## 9. Documentation Freshness

Quota安全仕様を変更する場合は、コード/workflowと同じPRで本ファイルを更新します。Run210 Documentation Freshness Guardにより、Flash 18回安全上限、Daily PAUSED、timeout fail-closed、Pending Retry fast lane等のCanonical契約が実装と矛盾した場合はCIを失敗させます。

Run261のArticle Model Routing authorityは`docs/reference/RUN261_LIVE_ROUTING_AND_FANOUT_REPAIR.md`、`docs/reference/RUN260_GEMINI_37_PRIMARY_38_QUALITY_RESCUE.md`、`run260_gemini_model_routing.py`です。
