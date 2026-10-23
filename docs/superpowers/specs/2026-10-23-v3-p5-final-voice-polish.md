# AIIF V3 P5 — Final conversational polish / output hygiene

Date: 2026-10-23
Status: EXPERIMENT ONLY, DRAFT, NOT CLEARED FOR PUBLICATION.

## Direct observations (not extrapolations)

The owner read the three real P5 C drafts from Run 39947881731 and judged the improvement substantial, while asking for another editorial improvement. Structural 16/16 PASS and 3/3 drafts does NOT establish factual accuracy or publication readiness.

Observed against the frozen experimental case payloads:

- FFT: visible technical contrast works, but invented personal history appears: 「以前は理論上の証明さえあれば進歩だと思っていた」. The input supports a technical contrast, not the Writer's past belief.
- Elastic Transformer: opening claims AI adoption always struggles with multiple model sizes and that costs swell in practice. The Evidence supports possible reduction in operating complexity, but not universal industry behavior. Keep the concrete playful 「計算量のつまみ」 mechanism.
- Claude Workspace: article claims historic adoption failures and generalized tab habits, neither documented by case Facts. Names specific Pro/Team/Enterprise plans although frozen Evidence says only 「有料プランユーザー」. Last paragraph contains Hangul syllable 의 embedded in Japanese: 「実務의スピード」.

These are observations about the actual generated drafts and locked experiment input, not independent verification of all vendor claims.

## Provider-free correction

This branch derives from previously successful P5 Preview H1 revision commit 70517ebc4ca028567e03b115bfe94eb25a1fb226, not temporary push proof workflow. Original frozen A/B and case payloads unchanged.

1. P5_FINAL_EDITORIAL_POLISH governs only C staged and bundled prose generation and final review. In the first 2–3 sentences, prioritize an evidence-supported concrete tension, then explain the mechanism with conversational and gender-neutral rhythm. Do not invent Writer biography, habitual user behavior, broad industry claims, unspecified product plans/prices, certain future outcomes or repetitive slogans.
2. C reader-facing article validation rejects Hangul syllables inserted directly inside a Japanese word, e.g. 「実務의スピード」. This is not a blanket foreign-language ban: separately spaced foreign terms are allowed, and exact supplied source quotations may be exempted once. Never auto-fix untrusted content.
3. Editorial diagnostics flag possible fabricated Writer history and unsupported grand predictions as non-gating human-review signals, never an objective quality score or source-truth proof.
4. Provider-free regression tests protect the B baseline, P5 two C routes, strict H1 full-manuscript review, legitimate source quotations, mixed script contamination and non-gating flags.

## Safety and acceptance

- No Gemini/provider call, further model stage, retry, fallback, Lite, production publishing, note, Notion, member DB, main or schema change.
- No loosening Evidence/Fact/Publication Gate or full-manuscript review.
- This patch changes the C prompt fingerprint: previous C drafts must not count as fresh validation. Freeze A/B, only request another C-only after separate user authorization and after 17:00 JST.
- Always disclose baseline model mismatch (A/B Gemini 3.8 Flash; latest C Gemini 3 Flash Preview).
- Human judgment against owner-approved Elastic Transformer exemplar decides quality GO: stronger beginning, approachable neutral voice, specific evidence and limits, no fictitious past, unsupported claims, or mixed-script defects.
- This draft remains unmerged. Temporary proof workflow branches must not be merged.
