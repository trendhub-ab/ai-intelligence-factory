# Run114 Product Review Reliability Validation

Date: 2026-08-23

## Scope

Run113実地Applyで確認した2つの損失を、Gateを緩和せずに修正した。

- `mlflow/mlflow`: Gemini成功後 `source-boundary unsupported named fact: MLflow Tracking` でFalse Reject。
- `zenml-io/zenml`: Gemini HTTP 200成功後、Product Review JSON parse errorで廃棄。

実地Artifactでは3候補すべてEvidence-readyでGemini 3 requestを消費し、保存はTraVEL 1件のみだった。Run114はこの2つの失敗経路だけを修正対象とする。

## Changes

### 1. Provider-enforced Product Review JSON Schema

`_call_product_review_pool()`に`response_json_schema`を追加した。既存`response_mime_type=application/json`と既存Model Pool/Request Budgetは維持する。

Schema固定項目:
- category
- adoption_score
- components (6 exact components)
- adoption_status
- evidence_confidence
- production_readiness
- main_risk
- best_for
- avoid_for
- short_rationale
- next_review_days

Google Gen AI Python SDKの現行公式仕様で`response_json_schema`がサポートされていることを確認した。
Reference: https://googleapis.github.io/python-genai/index.html#json-response-schema
Reference: https://ai.google.dev/gemini-api/docs/structured-output

### 2. Deterministic parser fallback + one logical retry

- `response.parsed`がdict/Pydantic dictなら優先。
- JSON textは通常`json.loads`。
- harmlessなcode fence / 前後transport textだけ0 APIで除去。
- 意味値の補完や欠損fieldの創作は禁止。
- それでもparse不能なら、同一候補について既存Product Review Request Budget内で論理retry 1回。
- retryは`review_slots_used`を増やさない。

### 3. Source-Boundary Reconciliation

`source-boundary unsupported named fact`のみを対象に、既に発見済みのfirst-party URLから0-Geminiで限定crawlする。

Safety:
- Assessment文を書き換えない。
- GitHub site-wide navigationを再導入しない。
- 明示済みHomepage/Docs/Primary SourceのみSeed。
- Seedと同じfirst-party host配下のみ追跡。
- unsupported nameに対応するlinkだけ追跡。
- 最大4 HTTP fetch/candidate。
- Full named factが取得本文に存在した時だけVerification Contextへ追加。
- その後にEvidence SufficiencyとDI Validatorを再実行。
- 未解決なら従来どおりFail-Closed。

## Falsification tests

Run114 dedicated: **11 / 11 PASS**

主な反証:
- JSON SchemaがProduct Review configへ渡る。
- Schema keywordがGoogle公式の対応subset（type/properties/required/additionalProperties/enum/minimum/maximum）だけで構成される。
- code fence/trailing textは追加APIなしで解析可能。
- provider parsed objectを優先。
- malformed JSONはlogical retry 1回で回復可能。
- MLflow Tracking型のFalse Rejectを明示済み公式Docsから解決可能。
- preflightで既に取得済みのDocs Seedでもlink discovery目的の限定再取得が可能。
- matching labelでも外部hostなら追跡しない。
- Reconciliation後の保存再試行でGeminiは2回目を呼ばない。
- 根拠未確認ならSource Boundary GateはFail-Closedのまま。

## Regression

- Run112 + Run113 + Run114 focused tests: **29 / 29 PASS**
- Full unittest: **521 / 521 PASS**
- Full pytest: **521 passed + 10 subtests PASS**
- Synthetic Full: **500 / 500 PASS**
- Synthetic critical failures: **0**
- Production write isolation: **true**
- `python -m compileall -q .`: **PASS**
- GitHub Actions workflow YAML parse: **6 / 6 PASS**

## Provider compatibility note

このコンテナは外部PyPIへ接続できず、`google-genai`実SDKをローカル追加installして型生成まで実行することはできなかった。一方、GitHub Actionsの直近Runは`google-genai 1.75.0`をinstallしており、現行Google公式SDK資料は`response_json_schema`を正式にサポートしている。したがってSchema fieldは公式API契約に沿う。次回GitHub Applyが実Provider E2E確認となる。

## Filename encoding regression

前版で文字化けしていた仕様書名を以下へ修正した。

`AI_Intelligence_Factory_最終仕様書.md`

Run114 packagingではUTF-8 filenameとしてZIP内の名前をfresh extraction後に照合し、旧mojibake名が存在しないことをRelease Gateに含める。

## Final package verification

- Fresh unzip SHA256 manifest: **2588 / 2588 PASS**
- ZIP integrity: **PASS**
- ZIP entries: **2589** (2588 hashed payload files + SHA256SUMS.txt)
- `AI_Intelligence_Factory_最終仕様書.md`: **present**
- ZIP UTF-8 filename flag for the Japanese specification filename: **true**
- Legacy mojibake filename `AI_Intelligence_Factory_µ£Çτ╡éΣ╗òµºÿµ¢╕.md`: **absent**
- Markdown UTF-8 decode check: **2041 / 2041 PASS**
