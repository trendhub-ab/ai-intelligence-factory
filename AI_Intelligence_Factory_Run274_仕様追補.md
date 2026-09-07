# AI Intelligence Factory — Run274 仕様追補

更新日: 2026-09-07

Run274の目的は、Fact / Evidence / Decision / Publication Gateを一切緩めず、実Productionで「読者価値まで通過するReady記事」を安定して生み出す確率を上げることである。Run272/273後のONE-SHOT実Artifactを反証材料とし、workflow greenではなくcurrent-policy Readyの実生成を最終評価対象とする。

## 1. 実Productionから確定した失敗構造

対象ProductionではDeep Dive候補5件に対してReady 0件だった。

- Evidence不足でGemini生成前に脱落: 2件
- Gemini model unavailableによるPending Retry: 2件
- Fact / Editorial / Publication / Evidenceを通過し、Reader ValueのみでNeeds Editorial Review: 1件

Reader Valueの実失敗fingerprintは以下。

- `dense_report_cluster`
- `repetitive_insight`
- `multi_axis_reader_weakness`
- `non_engineer_access_failure`
- final surfaceでのmulti-axis weakness
- final surfaceでのnon-engineer access failure

このため「Gateを下げる」「Reader向け指示をさらに大量追加する」は採用しない。

## 2. Reader prompt consolidation契約

Run226 / Run228は追加レイヤーを増やすのではなく、既存指示を短く優先順位化する。

1. 記事固有のReader Tension / Discovery / Decisionを1本選ぶ。
2. Fact / Evidence / required qualifier / 重要制約は残す。
3. Discovery・制約・Decisionのいずれにも影響しない周辺仕様、実装列挙、重複説明はARTICLEへ詰め込まない。
4. 専門語は普通の言葉で役割を先に示し、必要になった時だけ正式名称を出す。
5. 読みやすさは新しい説明・比喩・親しみ語の足し算ではなく、選択・順序・削除・言い換えで作る。

安全境界:

- SOURCE BOUNDARYを維持する。
- 新しいFact、数字、人物、会話、利用実績、因果、競合情報を作らない。
- Evidence条件・数値条件・反証・制約をReader Valueのために削らない。
- Reader Value Gate自体を緩めない。
- Reader-only失敗を理由とする通常Productionの追加Gemini retryは禁止するRun273契約を維持する。

## 3. Zero-API Evidence Backfill契約

従来は、Evidence preflightでGeminiを1回も使わず脱落した候補も `MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS` を1件消費していた。その結果、モデル予算を温存できていてもEvidence-ready候補へ到達する前に探索が止まる可能性があった。

Run274では新しいruntime layerを追加せず、既存のOperational Yield authorityである `run173_operational_yield.py` にbounded zero-API Evidence Backfillを統合する。

- 既存Funnelの `deep_dive_calls_avoided` が増えた場合だけ、ゼロモデル脱落と確定する。
- その場合だけcandidate attempt headroomを1件返す。
- デフォルトheadroomは最大5件、環境変数でも0〜8へclampする。
- 元のmodel-bearing attempt capは7件のまま維持する。
- Gemini global / per-model / Deep Dive run budgetは変更しない。
- Evidence Gate、Source Authority、Fact Gateを変更しない。
- regen/nonpersistent経路ではheadroomを変更しない。
- 新しいProduction funnelではheadroomをリセットする。
- `runtime_layers.py` / `production_pipeline.py` の既存runtime manifestは増やさない。

この方式により「Geminiを使わなかった失敗だけ探索枠を返す」ため、無料枠を増やさずBackfill到達確率だけを上げる。また既存Operational Yield層へ統合することで、同種の歩留まり制御を別wrapperへ分散させない。

## 4. 反証テスト契約

Run274は少なくとも以下を検証する。

- Evidence reject時にmodel call 0のままheadroomだけが1増える。
- model-bearing候補ではheadroomが増えない。
- headroomは設定上限を超えない。
- base model-attempt cap 7は変わらない。
- nonpersistent/regenではProduction headroomを変えない。
- 新しいrun/funnelで補償状態をリセットする。
- Run173内のRun274補償経路に新しいprovider/model/network call siteを追加しない。
- runtime manifestへ新規Run274 layerを追加しない。
- 実ProductionのReader Value failure fingerprintを既存Reader promptが直接扱う。
- Fact / Evidence / Decision / Source Boundaryを維持する。
- repository-wide regression / falsification / workflow safetyをすべて通す。

## 5. 完成判定

Run274の技術的完了と事業的完了を分離する。

### 技術的完了

- deterministic CI / repository falsificationがgreen
- existing model budgets unchanged
- Gate relaxationなし
- runtime manifestの不要な肥大化なし

### 事業的完了

次回Daily ONE-SHOT実Productionで、current publication policyに一致し、Fact / Evidence / Publication / Reader Valueを通過したReady記事が実際に生成されること。

Ready 0の場合はworkflow成功を成果扱いせず、最新Artifactの脱落reason codeから次の改善を決める。
