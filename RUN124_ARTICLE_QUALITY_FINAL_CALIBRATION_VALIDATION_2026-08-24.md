# Run124 Article Quality Final Calibration Validation — 2026-08-24

## Scope
Run123 Real Article Regressionで残った以下の4点のみを最小修正した。

1. `1リクエスト・1レスポンス`のprotocol patternをNumeric Evidence Claimから除外。
2. `WIMSE` ↔ `Workload Identity in Multi-System Environments`のcanonical alias binding。
3. AI Editorial Registerを、評価語＋説明型文末＋段階整理＋勧誘的締めの複合密度で校正。
4. 単発の自然な評価表現を過剰検知しないnegative fixtureを追加。

## Adversarial validation
- Run124 dedicated: **9/9 PASS**
- Mutation Negative-Control: **3/3 KILLED**
  - protocol-cardinality exception disabled -> detected
  - WIMSE canonical alias removed -> detected
  - editorial-register density gate disabled -> detected

## Full regression
- unittest: **623/623 PASS**
- pytest: **623 passed + 19 subtests PASS**
- Synthetic Regression self-test: **PASS**
- Synthetic Full: **500/500 PASS**
- Critical failures: **0**
- Major failures: **0**
- Production write isolation: **true**
- compileall: **PASS**
- Workflow YAML parse: **8/8 PASS**

## Provider-call invariants
- `_generate_via_chat(` production call sites: **7**
- `genai.Client(` production call sites: **1**
- Run124による追加Gemini call site: **0**

## Important limitation
この環境ではGitHub Actions上の実Gemini APIを使用したReal Article Regression E2Eは再実行していない。ローカル/adversarial/full syntheticのPASSと、Production Real Article E2EのPASSは区別する。Run124をmainへ反映後、Gemini API枠が利用可能な時点でReal Article Regressionを1回実施し、最終判定する。
