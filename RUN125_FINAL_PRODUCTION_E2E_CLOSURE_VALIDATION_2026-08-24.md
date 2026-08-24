# Run125 Final Production E2E Closure — Validation

## 反証で確定した根本原因
1. Run124のprotocol例外は`1リクエスト・1レスポンス`だけを想定していたが、実E2E稿は`1リクエスト・1ツール呼び出し`だった。
2. `JSON Schema`は一般技術仕様名だが、`Schema`がgeneric technical descriptorとして扱われず、Source Boundaryで第三者固有名に見える経路があった。
3. `monotonous sentence endings`は`ます/です`以外を全て`other`へまとめていたため、異なる常体文末を同一文末として数える設計バグがあった。

## 実装
- schematic protocol cardinalityをrequest-response/request-tool-callへ拡張。ただしstructural cue必須、rate/quota/latency/cost/capacity cueがあれば例外無効。
- `Schema / Format / Protocol / Specification`をgeneric descriptorへ追加。未知vendor名との組合せは依然Source Boundary対象。
- sentence-ending familyを明示分類し、unknown/other bucketを集計対象から除外。
- monotony Retryは語尾置換ではなく文リズム・情報順の局所再編集を要求。
- Run124の実MCP rejected稿をfixture化し、production `validate_fact_gate`経路を直接テスト。

## 検証結果
- Run125専用反証: 10/10 PASS
- Run121〜125連結記事品質反証: 49/49 PASS
- unittest discover: 633/633 PASS
- pytest: 633 passed + 19 subtests
- Synthetic Regression Full: 500/500 PASS
- critical failures: 0
- major failures: 0
- production write isolation: true
- Mutation Negative-Control: 3/3 KILLED
- 新規Gemini call site: 0

## Mutation Negative-Control
1. request-tool-call protocol例外を削除 → KILLED
2. generic `Schema` descriptorを削除 → KILLED
3. `other`一括monotonyロジックへ戻す → KILLED

## Production E2Eの扱い
この検証はローカル/決定論的反証であり、実Geminiを使うRun125 Real Article Regressionを実行済みとは扱わない。main反映後、GitHub Actionsの`Real Article Regression Test`で最終E2Eを確認する。

## Release validation
- compileall: PASS
- Workflow YAML parse: 8/8 PASS
- production `_generate_via_chat(` call sites: 7（Run124比増加なし）
- production `genai.Client(` call sites: 1（Run124比増加なし）
- Fresh unzip SHA256: 2639/2639 MATCH
- ZIP integrity: PASS
- Markdown UTF-8 decode: 2063/2063 PASS
- canonical `AI_Intelligence_Factory_最終仕様書.md`: present / UTF-8 filename flag PASS
- mojibake filename: 0
