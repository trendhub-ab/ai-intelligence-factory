# AI Intelligence Factory Run283 仕様追補

## 目的

Run282のCurrent-policy Ready Recoveryで、一次情報に明記されている数値が日本語表現へ自然変換された結果、Fact Gateが誤ってHARD BLOCKしたProduction事象を修正する。

対象となった実測例:

- 一次情報: `0.1x` input price → 記事: `10分の1`
- 一次情報: `an hour` / `1-hour` cache expiry → 記事: `1時間`

Run283の目的はFact Gateを緩和することではなく、**数学的・時間的に同値で、かつ局所的な意味も一致する表記差だけをfalse positiveから除外すること**である。

## Canonical implementation

`run283_numeric_evidence_equivalence.py`

Run283は歴史的な`runtime_layers.py::RUNTIME_LAYER_ORDER`へ追加しない。Run231で固定された互換runtime chainを変更せず、`production_pipeline.py`で**現行precision overlay**として次の順にinstallする。

1. 既存の`install_runtime_layers(pipeline)`を完了
2. `install_run283_numeric_evidence_equivalence(pipeline)`
3. Run268 / Run269等の現行strategy・precision overlay

これはRun268/269やReader precisionと同じ考え方で、Run282のProduction実測から追加された局所Fact precisionを、歴史的compatibility chainへ混在させないためである。

Run283は既存の`_find_unsupported_numeric_claims`だけをwrapする。Evidence閾値、Fact Gate全体、Reader Value、Publication Readiness、Decision Score、Retry回数、API budgetは変更しない。

## 許可する同値化

### 日本語分数 ↔ decimal multiplier

例:

- `10分の1` ↔ `0.1x`

ただし数値一致だけでは許可しない。

- pricing claimはpricing evidenceと一致すること
- performance claimはperformance evidenceと一致すること
- 特定domainが検出できない場合も、cache等の局所topic一致が必要

したがって、一次情報の`0.1x input price`を根拠に「速度は10分の1」を通すことは禁止する。

### 日本語の1単位期間 ↔ 英語の1単位期間

例:

- `1時間` ↔ `an hour` / `one hour` / `1-hour`

ただしcache expiry、runtime、timeout、session、retention等の**時間の意味**が一致する場合だけ許可する。

したがって、一次情報の「cache expires after an hour」を根拠に「処理時間は1時間」を通すことは禁止する。

## Fail-closed条件

以下はRun283で救済しない。

- 数値そのものが異なる
- `numeric condition mismatch`
- vague quantified claim
- hardware / dataset / metric condition mismatch
- actor mismatch
- unsupported named fact
- hype / guarantee
- Evidenceがmetadataにだけ存在し一次本文に存在しない場合
- 意味domain / time purposeが一致しない場合

## Publication Contract

`run283_numeric_evidence_equivalence.py`は公開可否へ影響するため`PUBLICATION_POLICY_FILES`へ含める。

したがってRun283の変更はPublication Policy SHAを更新し、過去Readyは現行policyとして自動継承されない。

`.github/workflows/note-ready-sync.yml`のpush pathにもRun283を含め、main反映時にzero-modelでNote Readyを再照合する。

Run283をhistorical runtime chainへ追加しないことはPublication provenanceを弱めない。`production_pipeline.py`自体とRun283 moduleの両方がPublication fingerprintの対象である。

## CI / regression

`tests/test_run283_numeric_evidence_equivalence.py`で以下を必須反証する。

- Run282実測の`10分の1 ↔ 0.1x`を救済
- Run282実測の`1時間 ↔ an hour`を救済
- pricingとperformanceの同値誤用を拒否
- cache expiryとruntimeの同値誤用を拒否
- wrong quantityを拒否
- 既存condition mismatchを絶対に救済しない
- install idempotency
- stdlib-only / zero-provider-call
- historical runtime chainを変更しない
- current precision overlayとしてのProduction install順
- Publication fingerprint / Note Ready reconciliationへの包含

required repository falsificationでもRun283テストを直接実行する。

## コスト・事業判断

Run282ではfalse positiveが不要なQuality Retryを誘発し、Gemini 3.8の503後に3.6 fallbackまで消費した。Run283により、根拠済み数値の表記差だけでRetryへ入る無駄を減らす。

一方、Reader Value / Human Appealの実質的な品質不足は一切救済しない。Ready率の数字を上げるために品質Gateを緩めない。

## 次のProduction検証

Run283をCI・mainへ反映した後、Run282専用Recoveryを**1件だけ**再実行する。

- fresh acquisition: OFF
- Screening: OFF
- Product Review: OFF
- recovery candidate: 1件
- model request hard cap: 4
- private note draft / VM / browser: OFF
- public publication: OFF
- Scheduled Daily: PAUSED維持

結果がReader Valueで失敗する場合は、その失敗を正として次の候補へ進むか、Reader生成品質を改善するかをコスト対効果で判断する。
