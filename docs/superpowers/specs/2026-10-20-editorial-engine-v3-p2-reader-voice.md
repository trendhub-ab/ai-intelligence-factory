# Editorial Engine V3 P2 — Reader Voice & Publication Boundary
Status: DRAFT / implementation contract (2026-10-20)
Base: V3 P1 editorial-quality branch, immutable head 69103a38abaf68764fd321ac9a5ef35d89b7f6ce
Evidence: C-only Run 39332120125 (3/3, gemini-3.8-flash, A/B byte-identical). Structural PASS does not mean editorial/publication PASS.

## Goal
Write readable, lively, personally voiced Japanese articles for note without invented experience or claims. Do not increase provider calls, relax Evidence/Fact/Publication Gates, or modify V1/V2 production.

## P2 requirements
1. **Reader-facing boundary:** Notion decision labels TRY / WATCH / PASS / AVOID and other internal classifications are metadata only. Never emit them as reader-facing article text, title, heading, or CTA. Do not blindly delete the ordinary English words when used as actual quoted source facts; distinguish standalone internal verdict labels from source-grounded vocabulary. Render the meaning in plain, case-specific Japanese supported by evidence. Keep internal classification unchanged in structured Notion fields.
2. **Distinctive first-person voice:** Keep a natural, gender-neutral 「私」 with theme-specific curiosity, a real question, and a visible evidence-driven change in interpretation. Do not fabricate product use, memories, meetings, feelings based on lived experience, or ungrounded prior beliefs. Never mechanically insert 「私は驚いた」 or increase first-person frequency as a proxy for voice.
3. **Plain, energetic Japanese:** Start with a concrete contrast, question, or consequence. Explain necessary technical terms immediately in everyday words; short paragraphs and varied sentence rhythm. Avoid stiff bureaucratic noun phrases, canned AI introductions, forced slang, gendered endings, and repeated templates. Preserve essential technical precision and numeric caveats.
4. **Reader value:** Go beyond feature description to show what changes, why it matters, limitations and a concrete next check, only to the extent evidence supports them. Do not invent scenarios presented as fact or infer unsupported causality.
5. **Variable structure:** Choose a topic-specific narrative path; headings where useful, not a rigid mandatory outline. Article text only: no internal pipeline stages, metadata, editorial verdicts, or planning artifacts.

## Implementation approach
- Apply the same P2 editorial constraints to both the staged article/review prompts and the bundled five-stage prompt. Maintain A/B experiment baselines.
- Preserve the exact Evidence / Facts / Sources boundary and the Fact-Safe Review step. Review must remove internal verdict leakage as a presentation defect, not change the underlying structured decision.
- Add offline deterministic regression tests that inspect both prompt paths for internal-label isolation, natural writer voice, no fabricated experiences, accessible language, and unchanged fact restrictions.
- Add negative fixtures containing internal classification tokens in structured decision context and positive fixtures where a source legitimately quotes a term. Verify only publication-facing text is sanitized, not evidence or Notion metadata.
- Keep model/API call budget unchanged. Run focused tests, then full offline regression and guards. No production Daily, note publishing, schema migration, or merge without explicit approval.

## Acceptance
- 0 internal verdict labels in publication-facing text across 3 C samples (unless explicitly source-grounded as ordinary vocabulary).
- 0 fabricated personal experiences and 0 unsupported factual claims on editorial review.
- Each C article has a distinctive, natural first-person viewpoint, a specific question, and an evidence-backed change in perspective; language understandable to non-specialist business readers.
- A/B baseline digests unchanged; no extra Gemini calls; no weakened Fact/Publication Gates.
- Final human editorial review of 3 C articles before declaring P2 publication-ready.
