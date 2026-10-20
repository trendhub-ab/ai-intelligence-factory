# Free Writer × Local Skills Guard — bounded experiment

Status: EXPERIMENT ONLY. No production integration, no note/Notion writes, no automatic publication.

## Hypothesis
Gemini can produce more engaging Japanese articles if it owns title, hook, structure, dialogue and voice; Local Skills owns evidence preparation and publication constraints, never rewrites prose.

## Input
Use the immutable Transformer case `3fa479ff-dca9-8194-a493-cb3a0d2b3a36` from `experiments/editorial_engine_v3_phase0/cases.py`. Keep the original Evidence, Facts and Sources unchanged. Do not add facts.

## Strict separation
1. **Local input**: extract evidence and sources offline. `local_skills.compiler.compile_snapshot` is a snapshot canonicalizer, **not** an article fact-checker; do not claim otherwise.
2. **Gemini**: one call, no retries; choose hook, headline, pacing, structure and natural neutral Japanese freely. No mandatory persona, five-stage output, scripted emotional arc, or fake first-person experience.
3. **Local output**: run existing `validate_article_layout` and `validate_reader_facing_article`; retain existing evidence/publication checks only where their input contracts genuinely match. Never rewrite generated prose. Unsupported facts require human review, not a fabricated machine PASS.
4. **Human**: review novelty, readability, engagement, accuracy, and whether the article would be worth opening on note.

## Acceptance
- Deliver a readable `.md` article and machine-readable `.json` report.
- Mark `HUMAN_REVIEW_REQUIRED` regardless of offline format pass.
- No API call before 17:00 JST; at most one Gemini generation; no retry, note draft, Notion write or main modification.
- Judge against reader value, **not** V1/V2 benchmark.
- Failure means do not deploy or expand into a new multi-stage engine.

## Minimal writer instruction
「与えられた検証済み素材だけを使い、AIの技術ニュースを大人の読者が思わず読み進める日本語記事にしてください。タイトル、冒頭、構成、会話、比喩、リズムは自由です。研究の単なる要約にしないでください。根拠のない事実・数字・体験談は作らず、不明点は不明と伝えてください。中性的で自然な言葉を使ってください。完成したMarkdown記事だけを出力してください。」
