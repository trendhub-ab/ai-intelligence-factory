# AIIF V3 P5 — Editorial Experience / reader-first discovery

Date: 2026-10-23
Status: **DRAFT · EXPERIMENT · NO-GO**. Human editorial acceptance required; neither production integration nor publishing is authorized.

## Decision and actual evidence

The owner read the three **real provider-generated** P4 C drafts and agreed with the evaluation: structurally valid but not yet compelling enough for note publication.

- Evidence: [P4 Run 39938411969](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/39938411969), artifact `12494971403`. Frozen A/B from historical Run `39239644474` used Gemini 3.8 Flash; this C-only run used **Gemini 3.6 Flash**. This is an explicitly mixed-model trial, never a clean same-model A/B comparison.
- Structural verdict: **16/16 PASS**, 3/3 C drafts, 3 logical provider calls, 4 attempts, 70 focused offline tests PASS. All three final Fact-Safe Review bodies exactly equal Persona Article Generation: Fact Review did **not** flatten these articles.
- FFT draft (948 characters): narrates prior personal expectations and formal conclusions rather than first showing the concrete theoretical/practical mismatch.
- Elastic Transformer (752 characters): opens with abstract claimed performance, repeatedly says what the writer found interesting, and states professional benefits rather than walking through the mechanism; it misses the previously owner-adopted benchmark beginning with a concrete curious question about flexible model sizes.
- Claude × Google Workspace (934 characters): explains integration, but spends space on self-reports and predictable benefits. A specific interaction between the Workspace document, sidebar and actual work would be a better reader-facing discovery **only to the extent supported by input Evidence**.
- The user-approved Forget-Only article written directly by the assistant earlier is a *qualitative comparator* only, not a V3 model output. Do not inject its prose, externally obtained facts, or samples into these three frozen experimental case inputs.

**Root diagnosis:** The current prompts repeatedly demand explicit Writer Reaction → before/after → first-person shift narration. The model often interprets this as article structure, despite repeated warnings not to. The improvement target is the **transition from editor planning to reader-visible evidence**, not more exclamation marks, youth slang or extra Gemini calls.

## P5 change scope

P5 branches directly from P3 SHA `03b3c237442c4c2b335440d363796c0def175c20`. It does not inherit P4's temporary push-trigger proof workflow.

1. In the *experimental C prompts only*, add one shared `EDITORIAL_EXPERIENCE_POLICY` for both staged Persona Article Generation and bundled single-call C, requiring evidence-supported reader entry -> concrete mechanism/conditions -> earned discovery -> bounded relevant next check. The story path is not a forced four-part published outline.
2. The Writer may express an actual evidence-triggered reaction with a gender-neutral `私`, but must not invent the writer's old beliefs, an earlier real-world experience or a retrospective conversion story. No invented experiments, figures, product usage or unsupported future consequences. Internal Reaction/Before/After remain planning artifacts.
3. Refine Editorial Discovery's `Narrative Path` to choose what the **reader sees** first and how actual evidence unfolds; do not serialize emotional planning labels or repeat facts to achieve target length.
4. In `reader_experience_audit.py`, flag **specific examples of formulaic self-narration** seen in real P4 drafts as a non-gating review aid. This is a literal surface diagnostic, not a quality score. It must not rewrite source paragraphs, decide factual correctness or authorize publication.
5. Keep the existing full-document Fact-Safe Review unchanged in substance, with its strict `Evidence / Facts / Sources` boundary, modality and causal strength limitations, internal-label isolation and fail-closed validation. P5 changes only phrasing around natural writer perspective, not the review safety standard.
6. Leave A, B, frozen cases, production writer, model/provider selection, checkpoint semantics, publication gate, Ready thresholds, Notion and note untouched.

## Offline tests / invariants

- Existing three-cases, immutable-input and B-prompt digest tests retain prior expectations.
- `test_v3_p5_editorial_experience.py`: P5 is present only in experimental C generation prompts, real evidence is shown before generic feelings, invented past beliefs are not forced, and the formulaic-language signal is diagnostic only.
- P3 tests must still pass and their lexical diagnostics must remain **insufficient to claim quality**.
- Whole repo pytest and workflow/reference/access Guards GREEN before any further provider trial.
- Since C prompt changes, its fingerprint changes. Old C completions cannot be reused as a fresh P5 proof. Preserve old A/B exactly, request fresh C-only separately.

## Editorial acceptance: human first, not a numerical hard gate

After explicit separately authorized post-17:00-JST bounded Gemini trial, evaluate three complete C articles **blindly against the fixed benchmark**:

1. Does the first paragraph pose a topic-specific question or concrete tension without empty hype?
2. Can a reader derive the insight by tracking the *actual evidence and conditions* instead of reading a declaration of the writer's surprise?
3. Are first-person sentences necessary, non-fabricated and free of template repetition?
4. Are numerical conditions, caveats, causal limits and comparisons faithfully preserved?
5. Does an adult operator or manager gain a naturally framed next check without sales hype or internal status labels?
6. Does the article read as **interesting** when compared with the owner-adopted Elastic Transformer exemplar, independent of structural pass?

Any boring, factually unsupported or synthetic-sounding C remains **NO-GO** regardless of diagnostics; no merge or publication until explicit human acceptance.

## Expense/security limits

- No added provider calls, extra model stage, API use or workflow dispatch in this P5 implementation.
- No scheduled task, main modification, publication, draft save, irreversible external mutation, or merging.
- P4 #5's 3.6 trial is historical evidence, not a green light for P5 writing.
