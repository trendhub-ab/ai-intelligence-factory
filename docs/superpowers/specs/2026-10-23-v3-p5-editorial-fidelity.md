# AIIF V3 P5.1 — reader discovery + scoped factual fidelity

**2026-10-23 · Experimental stacked change · NO MERGE / NO PUBLICATION**

Base: PR #852 at `95016a65701979063f56130bf181bca831661f5d`.
Replay proof: Run #39963513015, 3/3 C manuscripts, all structure checks PASS.
This proof is for the *prior* P5 source; it is not evidence that P5.1 is superior.

## Actual diagnosis from the completed C manuscripts

1. **FFT**: The article says `10の100乗` without identifying whether this is a company-verified constant, a critic's estimate, or another attribution. The immutable Phase 0 input itself contains this figure without its source's epistemic status. Prompt polishing *cannot* validate or correct possibly flawed upstream evidence. Human source verification is required before any publication.
2. **Elastic**: `50%削減で精度低下0.8%` appears without the model/task context. The arXiv abstract specifies DINOv3 ViT-H+/16, 50% sparsity, ImageNet-1k linear-probing accuracy. The frozen input lacks that granularity, so article generation must not invent missing qualifiers. Future evidence preparation should carry the verified metric's subject and conditions as structured source-backed facts.
3. **Claude for Google Workspace**: `有料プランなら追加コストなし` and `今日から過去` read as unconditional or exaggerated. Real plan availability, Google Workspace Marketplace permissions, and beta limitations should be validated at source-ingestion/publication time, not assumed as universal.

Real manuscripts also reuse generic reader-directed questions (`皆さんはどう感じますか`, `でも、ちょっと待ってください`) and writer-narration formulas (`私がここで一番気になったのは`). These are stylistic *review cues*, not publication disqualifiers on their own.

## Implemented narrow correction

- Tighten **the existing P5 final-polish passage** rather than add an extra model stage or growing instruction set. Surface a topic-specific contrast/mechanism early; keep the reader's discovery instead of the writer's emotional announcement.
- Preserve numeric applicability (subject/model, dataset, measurement, conditions) **only to the extent provided in input**. Do not reconstruct omitted experiment details from model knowledge.
- Attribute statement strength to the proper speaker: company statement, research claim, third-party criticism, or estimation. A cited criticism is not a verified company claim.
- Add three **non-gating** human editorial diagnostic cues for repeated stock phrasing. Never auto-rewrite a legitimate question.
- Keep existing Fact-Safe Review, source-lock, A/B freeze, Human Appeal and Publication Gates untouched. No Gemini call, model budget expansion, live publishing, note/Notion modification, or main change.

## Limits and acceptance criteria

- The new test module is provider-free and checks C-only prompt plumbing, preservation of A/B, and diagnostic review cues. Passing tests **does not establish** semantic fact-verification, evidence correctness, or a 90-point article.
- Frozen Phase 0 cases are intentionally unchanged for reproducible C-only comparisons. Before a *publishable* FFT/Elastic/Claude article, separately fix upstream evidence provenance with primary-source verification and repeat Fact Gate checks; do not silently mutate the frozen replay.
- No production/publication GO or auto-merge. Next optional proof requires separately authorized bounded C-only Gemini run after 17:00 JST, on this exact candidate commit with the same frozen checkpoint; compare blind outputs with the previous P5 Run, manually checking factual calibration, natural prose, and reader discovery.
