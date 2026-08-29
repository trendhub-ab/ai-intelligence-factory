# Run127 Intellectual Entertainment Pull Validation — 2026-08-25

## Scope
Run126 Reader Experience Intelligenceを基準に、追補「分かりやすい優等生から、続きを読みたくなる知的エンタメへ」を実装した。Fact / Evidence / Decision / Publication / Human Appealの既存HARD制約は緩和していない。

## Implemented
- Human Editorial promptへNarrative Pull、Article-Specific Angle、News Relevance、具体場面、中盤の説明書化防止、記事固有見出し、自然なDecision到達を追加。
- Reader-first「30秒でわかるこの記事」はUI要約として維持し、本文構造テンプレートとして扱わないことを明文化。
- 会社ネタ偏重を避け、生活例は理解改善に効く場合だけ選択。B2B専門テーマへ無理に挿入しない。
- `_reader_experience_signals()`へ以下のsoft-only診断を追加:
  - Narrative Pull
  - Article-Specific Angle
  - Everyday Bridge
  - Headline Pull
  - News Relevance
- 長い説明段落の連続、汎用見出しクラスター、ニュースフック不足、記事固有角度不足を監査Artifactへ可視化。
- Cross-Article Fingerprintへ「実は」「少し考えてみましょう」「○○に例えると」等の演出句signatureを弱い補助シグナルとして追加。単一/少数フレーズだけではReviewにしない。
- Notion DB schema変更なし。追加Gemini call siteなし。

## Falsification
Run127専用: 11/11 PASS。
- H: 分かりやすいが退屈な記事をsoft診断
- I: 会社ネタ中心でもB2B文脈ならHard化しない
- J: 汎用見出し群を検知し記事固有見出しは通す
- K: ニュースフック欠如を診断し、架空の「最新」理由は生成しない
- L: 過剰エンタメ/深刻テーマのtone mismatchを検知
- M: 横断演出句だけ一致ではHard化せず、構造同型との複合で既存Cross-Article Reviewへ寄与
- 具体場面によるNarrative Pull改善
- Article Auditへの新5軸出力
- Evidence safety / Gemini call site非増加

実装途中の反証では、同じ演出句2つを含むfixtureが構造・導入リズムまで同型だったためCross-Article Gateが発火した。fixtureを分離し、「演出句だけ同じならPASS」「演出句＋構造同型ならREVIEW」の両方向を固定した。

## Full regression
- unittest: 654/654 PASS
- pytest: 654 passed + 19 subtests
- Synthetic Full: 500/500 PASS
- Critical failures: 0
- Major failures: 0
- Production write isolation: true
- compileall: PASS
- Workflow YAML: 8/8 PASS

## Mutation Negative-Control
3/3 KILLED。
1. no-fabricated-freshness instruction削除 → Test K fail
2. generic heading cluster検出無効化 → Test H fail
3. cross-article rhetorical signature無効化 → Test M fail

## Cost / schema
- `_generate_via_chat(` call sites: 7（Run126同数）
- `genai.Client(` call sites: 1（Run126同数）
- New Gemini call sites: 0
- New Notion properties: 0
- Reader Experience remains soft-only; analogy/humor/everyday examples are not mandatory.

## Production completion rule
SyntheticのPASSだけで編集的完成とはしない。Gemini quota reset後のReal Article Regressionで、Accuracyに加えて「1段落目の後も読みたいか」「説明書感がないか」「小さな発見があるか」「見出しだけでも先が気になるか」「なぜ今読むか」「次も読みたいか」を人間監査する。
