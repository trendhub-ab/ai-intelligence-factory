# AIIF V3 P5 — Compact conversational prose (2026-10-23)

Status: experimental Draft, **not publication-approved**.

## Evidence and decision

The owner reviewed three genuinely generated C manuscripts from Run 39952607391 (Gemini 3 Flash Preview), and wants to continue improving. This run passed 16/16 structural proof checks and 3/3 outputs, yet Elastic Transformer became **more** stiff and report-like after increasingly verbose style instructions.

Examples from actual manuscripts:

- Elastic: 「AIを実際のサービスに組み込むとき、いつも悩ましいのが…」「これまでは…一般的でした」 — assertions of general practice absent from the frozen case facts; 「私が特に注目したのは」「非常に強力なメリット」「価値が十分にあります」 sound like a corporate report; the earlier useful analogy 「計算量のつまみ」 disappeared.
- FFT: compelling theoretical/practical contrast but 「今、私たちが取るべきアクション」 closing and unsupported general claim that AI is universally good at proof are stiff or ungrounded.
- Claude: lively introduction, but sweeping universal claims and product-cost framing remain a source-fidelity issue.
- Owner specifically asks whether **more conversational Japanese** could be easier to read. Editorial hypothesis: yes, provided the tone stays gender-neutral and technical evidence remains precise.

## Root-cause audit

The P5 prompt stacked several partially overlapping policies (P3 discovery, P5 editorial, P5 conversation, final polish) plus an article-stage mandate to carry four internal Writer planning fields into the published manuscript, and commands to lead to explicit Decision/Action. Repeating a prompt to be friendly while requiring reaction/before-after/decision reporting risks manufacturing a stiff report. No causal attribution to the prompt is proven from one model run.

## Implemented provider-free revision

Branch from P5 final-voice SHA 0d6cc620ff5a98ff6203726d102c5e4720a15b6f, distinct from single-shot trigger PR #849. No model calls.

1. Shorten overlapping C policies **in place**, retaining their separated responsibilities: reader can discover mechanisms; conversational distance/rhythm; evidence-grounded risk/claim checks. Keep existing policy names, stage keys and H1 full-manuscript schema.
2. Allow *more* colloquial Japanese: sometimes a short plain statement, sometimes a natural question, a small evidence-supported joke, and ordinary desu/masu where appropriate. Do not force fixed slang, fake teenage voice, gendered endings, identical article hooks, or categorical ban on politeness. The goal is a genuinely interested writer who can explain technical facts clearly.
3. Treat Writer Reaction, Writer Question, before/after and discovery as **editorial notes guiding what the reader sees**, not mandatory autobiographical sentences or fixed paragraph sections. Don't add fake 「私」 reactions to satisfy a checklist.
4. Preserve Decision/Action factual content and reader utility without requiring headings like 「今、私たちが取るべきアクション」 or a business-coaching call-to-action in every note article.
5. Leave strict Evidence / Facts / Sources boundary, no fabricated claims/habits/benefits, numerical qualifiers, Fact-Safe Review full-text inspection, H1 output format, Japanese/Hangul mixed-word hard guard, checkpoint fingerprint and frozen A/B untouched. P5 lexical cues stay **non-gating**.

## Checks and acceptance

- Provider-free regression for compact policy lengths, natural voice, frozen-B isolation, no forced writer biography, H1 and Fact-safe contracts.
- All existing 4k+ repository tests and guards required GREEN.
- **No automatic editorial GO from tests**; only actual regenerated C and human review against the 3 real prior outputs can establish improvement. Mixed-model disclosure is mandatory (A/B 3.8 Flash; C preview). Any future API generation needs separate user authorization after 17:00 JST.
- main, note, Notion, publishing workflow and Production untouched; this change remains Draft until explicit MERGE GO.
