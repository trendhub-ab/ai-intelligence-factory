# Run108 Human Editorial Naturalness Validation — 2026-08-23

## Objective
Remove visible AI-template prose while preserving fact safety, reader-first delivery, low operating cost, and the existing business pipeline.

## Changes
1. **Visible fixed-heading templates removed from generation prompt**
   - The five legacy display variants remain only as backward-compatible section aliases.
   - Gemini no longer receives a mandatory visible sequence such as `intro → conclusion → why → what → key → decision → final`.
   - Paragraph-by-paragraph role instructions (`1段落目`, `2段落目`, `3段落目`) were removed.
   - The model now receives only an internal editorial angle / opening cue / tone and must create content-specific headings.

2. **Editorial focus instead of equal-weight explanation**
   - Prompt explicitly requires one main takeaway and permits omission/compression of low-value background.
   - Generic transition glue, repeated contrast molds, uniform section length, repetitive sentence endings, and mechanical enumeration are discouraged.

3. **Zero-API composite AI-style detector**
   - Signals: repeated generic transitions (`ここで重要なのは`, `注目すべきは`, `ポイントは`, `つまり`, `言い換えると`), repeated `という点です`, repeated `Aではありません。Bです。`, enumeration molds, reuse of multiple legacy template headings, generic-heading density, staccato short-sentence bursts, and suspiciously uniform section lengths.
   - A single stylistic device never blocks publication. Only a high-confidence combination (`score >= 5`) becomes `ai_style_composite_high`.
   - High composite is **REVIEW**, not HARD Fact failure.

4. **Targeted existing quality retry**
   - The detector itself adds **0 API calls**.
   - Only a materially formulaic article may consume the already-existing single quality-retry path.
   - Retry may change headings / paragraph breaks / rhythm, but may not change or add facts, numbers, entities, Decision meaning, or evidence qualifiers.

5. **Free-heading structure compatibility**
   - Fact Gate no longer forces legacy heading strings when the article has a natural lead, multiple content-specific headings, and a concrete decision near the end.
   - Legacy articles remain backward compatible.
   - Human Appeal opening inspection now reads the actual unheaded lead or first content-specific section.

## Adversarial validation
- Deliberately formulaic prose that previously passed (`ここで重要なのは` repetition + generic template headings + enumeration + contrast mold) is now detected as `ai_style_composite_high` and routed to REVIEW.
- A natural Kobo/Cobalt-style sample with uneven paragraphs, content-specific headings, one clear editorial focus, and a concrete trial decision does **not** false-positive.
- A single copywriting contrast (`Aではありません。Bです。`) does **not** trigger the composite.

## Regression results
- Run108 dedicated tests: **8 / 8 PASS**
- Full unittest discovery: **456 / 456 PASS**
- pytest: **456 passed + 10 subtests**
- Synthetic Full: **500 / 500 PASS**
- Synthetic critical failures: **0**
- Synthetic major failures: **0**
- Production write isolation: **true**
- compileall: **PASS**
- GitHub Actions workflow YAML: **5 / 5 PASS**

## Unchanged
- Fact Gate safety principles
- Evidence Sufficiency / Source Boundary
- Publication Readiness safety
- Notion persistence and product DB logic
- Deep Dive request caps / persistent Gemini budget
- Source ROI / ranking logic
- Reader-First 30-second summary and source card
- Eyecatch Run106 vertical/horizontal centering
