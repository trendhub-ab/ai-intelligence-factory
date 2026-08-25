# Run123 Article Quality Finalization — Validation

Date: 2026-08-24  
Baseline: Run122 Real Article Regression Hardening

## Trigger
Run122後のGitHub Actions Real Article Regressionは1/3 Acceptedだった。

- ESP32 / Docker Sandboxes: Accepted。ただし「第一の柱」「実務的な示唆」「最も興味深い」「第一段階/第二段階」「妥当な判断と言えます」等が一稿に集中し、AI的な整理語彙密度が残った。
- Kobo / Cobalt: `article_structure_needs_edit`。実稿では内容固有のセクション名が複数存在するが、Markdown `###`だけが欠落していた。
- MCP Roadmap: `unsupported numeric claim: 5分`。実際は「5分野」であり、時間5分ではない。

## Implemented logic
1. 厳格な0-API plaintext-section → Markdown heading修復。候補2個以上、空行独立、短い日本語label、直後に十分な本文がある場合だけ実行。
2. 日本語Numeric boundaryを修正し、`5分野/5分割/5分布/5分類/5分岐/5分析`を時間単位`5分`と誤認しない。実際の`5分で完了`は引き続き検査する。
3. AI Editorial Register Densityを追加。禁止語ではなく、高密度・多様性＋段階列挙等のcompanion signalでのみHigh。
4. PromptでMarkdown `##/###`明示とEditorial Register stacking抑制を追加。
5. Structure Retryから旧固定見出し名要求を排除。

## Real-fixture deterministic replay
- 前回ESP32 Accepted稿: Editorial Register count=7、distinct=6、ordinal framing=3 → composite high=true。
- 前回Kobo Rejected稿: 0-API修復で複数の裸セクション名を`###`へ昇格。単独の曖昧行は昇格しない。
- 前回MCP Rejected稿: `5分野`はtime numeric claimとして検出されない。

## Dedicated falsification
Run123 dedicated tests: **10/10 PASS**.

Coverage includes:
- `5分野` false positive blocked
- real `5分` remains checked
- other `分` compounds are not time claims
- multiple unmistakable naked section labels are repaired
- one ambiguous label is not repaired
- AI editorial register high-density + ordinal framing is reviewed
- one editorial phrase is not blacklisted
- prompt requires Markdown heading markers without fixed names
- prompt discourages register stacking while allowing single use
- structure retry does not reintroduce legacy heading names

## Mutation Negative Controls
**3/3 KILLED**.

1. Broaden minute matching so `5分野` becomes `5分` → killed.
2. Permit a single ambiguous plaintext label to become a heading → killed.
3. Disable Editorial Register composite contribution → killed.

## Full regression
- unittest: **614/614 PASS**
- pytest: **614 passed + 19 subtests PASS**
- Synthetic Regression self-test: **PASS**
- Synthetic Full: **500/500 PASS**
- Critical failures: **0**
- Major failures: **0**
- Critical invariants: **PASS**
- Production write isolation: **true**
- compileall: **PASS**
- Workflow YAML parse: **8/8 PASS**
- Production `_generate_via_chat(` call sites: **7**
- Production `genai.Client(` call sites: **1**

## Production-E2E boundary
No live Gemini API call was made for this local finalization. Run123 is locally/adversarially validated, but the same GitHub Actions `Real Article Regression Test` must run after main integration before claiming Production E2E completion.
