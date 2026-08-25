# Run115 Product Review Adversarial Hardening Validation

Date: 2026-08-23

## Status

**Completed candidate package / not yet declared Production-deployed.**  
Run114独立監査で見つかった反証テストの死角を修正し、実装・テスト・Mutation Negative-Control・全回帰を再実行した。実Provider E2Eは次回GitHub Bootstrap Applyで確認する。

## Root causes falsified

### 1. Redirect trust-boundary gap
Run114はSeed/request URLのfirst-party判定をしていたが、HTTP 30x後の`final_url`を再判定していなかった。first-party Seedからthird-partyへredirectした本文にnamed factが存在すると、Source-Boundary Reconciliationが誤って解決済みになり得た。

Run115では`final_url` hostをSeed hostに対して再検証し、範囲外なら本文・link・Evidence追加を破棄して`redirect_outside_first_party`を監査記録する。

### 2. Provider JSON Schema != local trust boundary
Run114はprovider Structured Outputを導入したが、application parser側は欠損field等をdefault/空値へ落とせる余地があった。Run115は保存前のSemantic Schema validationを独立実装した。

Local validation:
- required fields exact
- additional fields rejected
- enum strict
- 6 component keys exact
- integer/range strict; bool rejected
- component total == adoption_score
- required text non-empty
- next_review_days 7..60
- invalid category is not silently normalized to OTHER

Semantic failureもJSON syntax failureと同じく、既存Product Review budget内で同一候補1回だけstructured retry対象。

### 3. Budget test was strengthened from logical mock to real counters
Run114のretryテストだけではProduct Review budget実消費を直接証明できなかった。Run115では`ProductReviewRequestBudget`と`GeminiBudget`を実オブジェクトで使用する。

- budget=2: initial 1 + structured retry 1 = **2 consumed**
- by_kind: `product_review=1`, `product_review_retry=1`
- global Gemini request_count = **2**
- budget=1: initial後はstructured retryを送信せず、2個目のfake provider responseが未使用のまま残る

## Prompt/schema separation
Output keys / enums / rangesの一覧をPromptから除去し`response_json_schema`へ集約。Promptには一次情報限定、Category判断原則、component合計、ADOPT条件などDecision semanticsのみを残した。

## Dedicated adversarial tests

Run115 dedicated: **9 / 9 PASS**

Cases include:
- Semantic Schema: missing / unknown enum / extra / component missing / range / sum mismatch / bool / blank / review range
- invalid Category must fail, not normalize
- provider `parsed` Semantic failure must not silently fall back to a different `text` payload
- Prompt/schema duplication regression
- real local HTTP redirect to different host with named fact in redirected body
- same-host redirect remains eligible
- real Product Review budget consumes 2 for one logical retry
- budget=1 blocks provider send #2
- valid structured payload remains compatible

## Mutation / Negative-Control

Release候補コードを一時的に3箇所破壊し、対応テストが本当に赤になることを確認した。各Mutation後はbaseline sourceへ復元し、SHA256一致を検証した。

1. **Redirect final-host guard disabled** -> redirect adversarial test FAILED as expected.
2. **Category enum guard disabled** -> invalid-category test FAILED as expected.
3. **Product Review can_request always true** -> real-budget cap test FAILED as expected (`used 1 != 2`).

Result: **3 / 3 mutations killed**.  
Restored `pipeline.py` SHA256: `4f978c7dbbc4d6ae55939c923595881af05d3daf02effc805b1d4b953b289a5d`.

## Focused regression

Run112 + Run113 + Run114 + Run115: **38 / 38 PASS**

Run112の旧「unknown Category -> OTHER」期待値はRun115の明示契約と衝突するため、削除ではなく「unknown Category -> schema failure」へ更新した。これはテスト都合の緩和ではなく、silent coercionを禁止するFail-Closed契約変更。

## Full regression

- Full unittest: **530 / 530 PASS**
- Full pytest: **530 passed + 19 subtests PASS**
- Synthetic Full: **500 / 500 PASS**
- Synthetic critical failures: **0**
- Synthetic major failures: **0**
- Production write isolation: **true**
- `python -m compileall -q .`: **PASS**
- GitHub Actions workflow YAML parse: **6 / 6 PASS**

Synthetic Fullは`SYNTHETIC_REGRESSION_MODE=true`のoffline import-only google.genai stubを使用し、provider/Notion/publishing writesを行わないproduction-isolated validatorとして実行した。

## Scope control

Run114からproduction codeで変更した中心は`pipeline.py`のみ。Run115ではProduct Review hardening以外の通常Daily acquisition/article logicを意図的に変更していない。Run112 compatibility testはCategory contract変更に合わせて期待値を厳格化し、Run115専用test fileを追加した。

## Filename / encoding release gate

- Canonical specification filename: `AI_Intelligence_Factory_最終仕様書.md`
- Legacy mojibake filename prohibited: `AI_Intelligence_Factory_µ£Çτ╡éΣ╗òµºÿµ¢╕.md`
- All Markdown files must decode as UTF-8 before packaging.
- ZIP Japanese filename UTF-8 flag and fresh extraction are verified during final package generation.

## Remaining live verification

Local test suite cannot prove real Gemini structured-output behavior or live first-party HTTP behavior under GitHub Actions secrets/network. Therefore Run115 is a **completed candidate** until one controlled Bootstrap Apply confirms:

- `structured_retries` / `structured_retry_recovered`
- `boundary_reconciliation_attempted` / `boundary_reconciled`
- Product Review request budget actual usage
- saved/skipped reasons
- Category / History / Subscriber synchronization

No Quality/Evidence gate should be loosened to force inventory growth.
