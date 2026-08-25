# Run112 — Product Review Category Resolution Validation

## Scope
Run111を基準に、**Product ReviewでASSESSED化したレコードのCategoryがLegacyの`OTHER`を引き継ぐ問題だけ**を修正した。

変更対象:
- `pipeline.py`
- `tests/test_run112_product_review_category_resolution.py`（新規）

変更していない領域:
- Inventory Bootstrap Plan / Portfolio ranking
- ArXiv Practical Artifact Gate
- Adoption Score / Adoption Statusの算定条件
- Evidence Sufficiency Gate
- History transaction
- Subscriber syncロジック
- 通常Daily収集 / Screening / Calibration
- 記事生成 / Fact / Editorial / Publication / Human Appeal Gate
- Gemini model pool / request budget / persistent counter

## Root cause
Product Review用Gemini JSONに`category`を要求していなかった。
`run_product_reviews()`は保存時に既存TechnologyレコードのCategoryを`portfolio_topic`として渡していたため、Legacyが`OTHER`ならASSESSED後も`OTHER`のまま残った。

## Fix
既存Product Review 1リクエストのJSON schemaに`category`を追加した。追加Geminiリクエストは発生しない。

Categoryの許可値:
- MODEL
- AGENT
- DEVTOOLS
- INFRA
- DATA
- SECURITY
- MULTIMODAL
- PRODUCT
- OTHER

判定ルール:
1. Source種別やLegacy Categoryをコピーしない。
2. verified primary source contextで確認できる主用途・主機能だけから1つ選ぶ。
3. 複数候補が同程度、根拠不足、未知値なら`OTHER`へFail-Closed。
4. 保存時はProduct Reviewが返した正規化済みCategoryを使用する。
5. Planのplanning_categoryはauthoritative Categoryとして無条件コピーしない。

## Falsification tests
- valid `data` -> `DATA`
- unknown `DATABASE` -> `OTHER`
- missing category -> `OTHER`
- promptがclosed taxonomy + ambiguity fallbackを要求
- Legacy `OTHER`でもProduct Review `DATA`を保存コンテキストへ渡す

## Verification
- Run112 targeted tests: **5/5 PASS**
- Full unittest: **497/497 PASS**
- pytest: **497 passed + 10 subtests**
- compileall: **PASS**
- Synthetic Full: **500/500 PASS**
- Synthetic critical failures: **0**
- production_write_isolation: **true**
- GitHub Actions YAML parse: **6/6 PASS**

500/500全件PASSのためSynthetic major failureも0。

## Live data correction
既にRun111 ApplyでASSESSED化済みだった `github:huggingface/datasets` は、一次情報とProduct Review内容からDATA分類が明確なため、既存レコードだけを補正した。
- Technology Intelligence DB: `Category OTHER -> DATA`
- AI Decision Intelligence: `Category OTHER -> DATA`

Adoption Score / Status / Evidence / History / Reviewed Atその他の値は変更していない。

## Release decision
PASS。Run111からの局所修正としてリリース可能。
次回Product Review以降は、ASSESSED化時に同じGeminiレスポンス内でCategoryも確定するため、Legacy `OTHER`の機械的継承を防止する。
