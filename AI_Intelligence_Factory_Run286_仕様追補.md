# AI Intelligence Factory Run286 仕様追補

## 目的

Current-policy Ready Recovery #3後の実運用観測で、Content Intelligence DBのReady件数が直後は46件、その後45件へ収束した。最終的には `stale=40 + unsupported=5 = 45` と完全一致し、恒久的な未分類行は存在しなかった。

この挙動は、NotionのDB query結果と個別page readの間に短時間の整合性差があり得ることを示す。Run286はこの差を理由にGeminiを無駄打ちしないことを目的とする。

## 変更1: Recovery候補のlive Article Status再確認

Run282の既存selectorが、persisted business value・source allowlist・license・Publication Contract stalenessから候補を1件選んだ後、Run286がそのpageを直接readする。

生成へ進める条件は次の1点を追加する。

- live `Article Status == Ready`

以下はすべてfail-closedで候補0件として終了する。

- DB queryではReadyだがdirect page readではPending Retry / Needs Editorial Review / その他
- direct page read失敗
- status空
- page id不正

このguardはモデル呼出前に動作するため、Notionの短時間stale readだけを理由にGemini requestを消費しない。

## 変更2: Recovery直後のNote Ready整合性観測

専用Recovery workflowに限り、生成ステップ終了後のNote Ready reconciliation前にReady source queryを2回read-onlyで観測する。

- probe 1
- 2秒待機
- probe 2
- 2秒待機
- 従来どおり `note_ready_sync.py` を1回実行し、その最終結果だけで成功判定

probeはsource DB read-onlyであり、destination writeやmodel requestは行わない。通常のNote Ready push sync、Daily、通常Productionには追加read/待機を導入しない。

## Publication / Qualityへの影響

変更しない。

- Fact Gate
- Reader Value / Human Appeal Gate
- Publication Readiness
- Evidence Sufficiency
- Publication Contract fingerprint
- title/body/eyecatch bytes
- Gemini model routing
- request budget
- current-policy recovery hard cap 4 requests
- Reader-only repair hard cap 1
- Draft / VM / browser / public publication boundary
- Daily PAUSED

Run286は既にnon-publication controllerとして分類済みの`current_policy_ready_recovery.py`内部だけから利用する。`production_pipeline.py`のbytesは変更せず、Publication Contract fingerprintを不要に変化させない。

## コスト判断

狙いはyield向上より先に無駄requestの防止である。live statusがReadyでなければ、そのONE-SHOTでは次候補へ進まず0件終了する。これは候補選定を強引に継続してGeminiを消費するより、現在のFree Tier優先方針に合う。

次回明示Recoveryで初めて実Notion + Gemini経路を検証する。Run286実装・PR・CI・mergeまではGemini APIを使用しない。
