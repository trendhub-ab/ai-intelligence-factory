# Run116 Bounded First-Party Discovery Validation

Date: 2026-08-23

## Status

**Completed candidate package / not yet declared Production-deployed.**
Run115の実Applyで残ったSource-Boundary ReconciliationのRecall不足だけを修正した。Quality/Evidence Gate、Gemini budget、通常Dailyを緩めていない。実GitHub Actions + live MLflow E2Eは次回Bootstrap Applyで最終確認する。

## Live failure reproduced from Run115 artifact

Run115 Applyでは`mlflow/mlflow`がEvidence-readyかつGemini Product Review成功後、`source-boundary unsupported named fact: Tracking Server`でRejectされた。Reconciliationは`attempted=1 / reconciled=0 / fetches=4`だった。一方、2026-08-23時点のMLflow公式Docsには`MLflow Tracking Server`の専用ページが存在するため、Gateの安全性ではなくfirst-party docs discoveryのRecall不足と判定した。

## Run116 implementation

### 1. Explicit seed first
- 既に取得済みの公式Homepage / Docs / Primary SourceだけをSeedにする。
- Seed本文は最大2件。
- Seedが露出するsame-first-party matching linkをsitemapより優先。

### 2. Bounded sitemap discovery
- Seed pathから`/docs/latest/sitemap.xml`等を決定論的に作る。
- Discovery fetch上限: **3**。
- Sitemap URL inventory上限: **1,200**。
- Ranked page候補上限: **4**。
- Sitemap indexのsame-first-party child sitemapは、未確認の推測sitemapより先に処理。
- Third-party sitemap URLはparse時点で除外。
- Discovery XMLはEvidence documentへ入れない。

### 3. Bounded body fetch
- Seed / direct child / sitemap candidateを合計したHTML/text body fetch上限: **6**。
- final redirect hostを再検証しfirst-party外なら本文・link・Evidenceを破棄。
- URL lexical matchだけでは解決しない。
- 本文内にnamed factのfull token sequenceが存在した場合だけEvidenceへ追加。
- `Tracking Serverless`は`Tracking Server`の根拠として不採用。

### 4. Zero Gemini reconciliation
- Reconciliation中のGemini requestは0。
- Production `_generate_via_chat` call sites: Run115 **7** -> Run116 **7**。
- `genai.Client` production sites: Run115 **2** -> Run116 **2**。
- Reconciliation成功後は同じparsed AssessmentをEvidence/Validatorへ再投入し、追加Product Review requestを送らない。

## Dedicated falsification

Run116 dedicated: **10 / 10 PASS**

Cases:
1. MLflow相当のversioned docs sitemapから`tracking-server`公式ページを発見し解決。
2. URLが`tracking-server`でも本文に完全名がなければFail-Closed。
3. third-party sitemap URLをrank/fetchしない。
4. sitemap indexのfirst-party childをbounded budget内で優先追跡。
5. 多数候補があってもbody fetch ceilingを超えない。
6. hard body cap=3をテスト時に設定し、実fetchも3で停止。
7. sitemap XMLはEvidenceへ入らない。
8. `Tracking Serverless` prefix誤一致を拒否。
9. 現在のMLflow公式path形`/docs/latest/self-hosting/architecture/tracking-server/`をhard-codeなしで高くrank。
10. `run_product_reviews()`統合で initial Reject -> bounded discovery -> revalidation save、Product Review Gemini callは1回のまま。

## Negative-Control / Mutation

Run116 production candidateを一時的に破壊し、対応テストが赤になることを確認。各mutation後にbaseline `pipeline.py` SHAへ完全復元。

1. third-party sitemap filter disabled -> **KILLED**
2. named-fact phrase proof disabled -> **KILLED**
3. sitemap-index child priority disabled -> **KILLED**

Result: **3 / 3 mutations killed**。
詳細: `RUN116_MUTATION_NEGATIVE_CONTROL_2026-08-23.log`

## Full regression

- Full unittest: **540 / 540 PASS**
- Full pytest: **540 passed + 19 subtests PASS**
- Synthetic Full: **500 / 500 PASS**
- Synthetic critical failures: **0**
- Synthetic major failures: **0**
- Production write isolation: **true**
- `python -m compileall -q .`: **PASS**
- GitHub Actions workflow YAML parse: **6 / 6 PASS**

## Scope control

Run115からproduction codeで変更した中心は`pipeline.py`のみ。
以下はRun115とbyte-identical:
- `decision_intelligence.py`
- `inventory_bootstrap.py`
- `subscription_attribution.py`
- `regression_suite.py`
- `.github/workflows/daily.yml`
- `.github/workflows/inventory-bootstrap.yml`

追加したのはRun116専用test・validation・operations・mutation log、および最終仕様書のRun116節。

## Filename / encoding release gate

- Canonical: `AI_Intelligence_Factory_最終仕様書.md`
- Mojibake filename prohibited.
- 全Markdown UTF-8 decode。
- ZIP Japanese filename UTF-8 flag / fresh extract / SHA256を最終packageで再検証する。

## Remaining live verification

ローカル環境は外部DNSが使えないため、MLflow公式siteへのruntime HTTP fetchそのものはGitHub Actionsでしか最終証明できない。Web調査上は2026-08-23時点で公式ページ`/docs/latest/self-hosting/architecture/tracking-server/`が存在することを確認済み。次回Bootstrap Applyで以下を確認する。

- MLflowが再度候補になった場合: `boundary_reconciliation_attempted=1`, `boundary_reconciled=1`
- Reconciliation logの`discovery_fetches <= 3`, `body_fetches <= 6`
- Product Review Gemini requestがReconciliationによって増えない
- MLflow Assessmentが全Gateを通る場合のみNotion/History/Subscriberへ保存
- 他候補のsaved/skippedとProduct Review budget実消費
