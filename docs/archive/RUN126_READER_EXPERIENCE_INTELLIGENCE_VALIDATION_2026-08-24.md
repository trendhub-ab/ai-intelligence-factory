# Run126 Reader Experience Intelligence Validation — 2026-08-24

## Scope
Run125 Production Baselineに、知的エンタメ × Decision Intelligence方針を追加。Fact/Evidence/Decision Gateは変更せず、生成編集方針と0-API Reader Experience監査を追加した。

## Implemented
- Human Editorial promptへAccessibility / Curiosity / self-relevance / optional analogy / serious-topic tone / return-pull方針を追加。
- 読者定義を「主対象は意思決定者だが専門知識を前提にしない二層構造」へ更新。
- `_reader_experience_signals()`を追加。
- Article AuditへReader Experience 7項目を追加。
- Reader Experienceはsoft-onlyで、既存GateへHARD FAILとして接続していない。
- Notion DB schema変更なし。
- Gemini call site追加なし。

## Falsification
Run126専用テスト 10/10 PASS。
- 比喩なし良質記事が許容される
- 比喩過剰をsoft warning
- Security等で軽薄比喩を強制しない
- 未説明略語をsoft診断
- 正式名称→略称の説明済みケースを誤検知しない
- 発表要約だけの導入をsoft診断
- reader bridge / return pullを観測
- Article AuditへReader Experienceを出力
- SOURCE BOUNDARY / Evidence-to-Decision指示維持
- Gemini call site不増

実装途中の反証で、正式名称（WIMSE）の後に略称を括弧提示する自然な説明を未説明扱いするFalse Positiveを発見し、修正後に10/10 PASSを確認した。

## Full regression
- unittest: 643/643 PASS
- pytest: 643 passed + 19 subtests
- Synthetic Full: 500/500 PASS
- Critical failures: 0
- Major failures: 0
- Production write isolation: true
- Mutation Negative-Control: 3/3 KILLED

## Cost / schema
- `_generate_via_chat(` call sites: 7（Run125同数）
- `genai.Client(` call sites: 1（Run125同数）
- New Gemini call sites: 0
- New Notion properties: 0

## Production completion rule
Syntheticだけで編集的完成とは判定しない。Real Article Regressionで異なる記事タイプを確認し、Accuracyに加えて「最後まで読みたいか」「専門書なしで理解できるか」「少し詳しくなれたか」「また読みたいか」を人間監査する。
