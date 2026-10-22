# V3 P3 — Reader experience continuity and additional Forget-Only comparator
Date: 2026-10-22
Status: EXPERIMENTAL / DRAFT / NO-GO. No publication or Production integration.

## Why
The owner found the assistant-written, V3-logic-inspired Forget-Only rewrite (authored directly in chat, not emitted by the V3 runtime) “遥かに面白く読めます” compared with the V1 note article, but that rewrite was **not** the result of executing the V3 provider workflow. The original Elastic Transformer benchmark remains the accepted quality reference; this Forget-Only example is an additional **reader-positive qualitative comparator**, not a substitute or a claim of provider-model improvement.

The V3 architecture already asks for five stages and preservation of Writer-owned Reaction, Question, Evidence-caused Cognitive Shift, and Discovery. However, structured pipeline checks can pass with a flat final article. P3 therefore makes *loss of these signals* observable rather than adding yet another long prompt or another provider call.

## Grounded references
- Original V1 article: Content Intelligence page `3f4479ffdca981ca9220cf15ac374db6`; held article intentionally withdrawn from note, remains in Notion.
- Reader-positive human-created draft: 2026-10-22 chat, “AIに『これ、忘れて』と頼む。なのに、なぜ記憶が必要なの？”.
- Grounding: [Why Forget-Only Unlearning Needs Memorization](https://arxiv.org/abs/2610.10519v1).
- Previously adopted quality reference: Elastic Transformer article / user-selected sample; **not modified by this change**.
- Prior 3-case Phase 0 immutable A/B comparator: FFT, Elastic Transformer, Claude in Workspace. Do **not** insert Forget-Only as fourth case into the 3-case checkpoint or change A/B identity/digests.

## Qualitative comparator: what made Forget-Only readable

### Opening tension
V1 begins with `どんな内容？ / なぜ重要？ / 結論は？` and supplies the abstract conclusion early. The positive sample instead lets the reader encounter the paradox, “忘れるために、もっと覚えておかなくちゃいけない？”.

### Actual evidence-driven understanding
The scene is NOT a fabricated product-use story: the writer compares two hypothetical histories yielding the same trained AI, then asks why deleting the same item can have *different correct retraining outcomes*. The reader discovers why same model + same deletion data can be insufficient.

### A visible intellectual change
Before: “消したい情報が分かれば消せる”.
After: “削除後、どんなAIになっているべきかを知ることも必要”.
This change is supported by the study’s specific conditional theoretical setup, not a universal claim about all LLMs.

### Concrete adult decision
Distinguish output suppression from verified exact unlearning and confirm the scope, evaluation method and data-retention constraints. Do not pretend all providers, products or laws have been tested.

## What is implemented
- `reader_experience_audit.py` measures whether the final C article *visibly* contains a first-person Writer, a question, source-specific planning phrase overlaps, and whether Fact-Safe Review removed the voice.
- Output `c_reader_experience_diagnostics.json` is generated with existing blind artifacts, without modifying any article, A/B comparator, official gate, checkpoint, model budget or workflow.
- For C-only partial runs, emit diagnostics **only for verified completed current cases**, never stale checkpoint artifacts.
- Heuristic statuses: `surface_present`, `review_for_possible_loss`, `not_evaluable`. No semantic entailment or “interestingness” is inferred from text similarity.

## What is NOT proved
- Human praise of the offline rewrite is **not** proof that Gemini/V3 can reproduce it.
- Surface overlap does not prove that an Evidence-caused insight survives; absence of word overlap does not prove it was lost.
- A diagnostic with no flags is **not** a quality pass, Fact/Evidence pass, publication permission or a production GO.

## Next real quality experiment
After 17:00 JST and explicit separately authorized budgeted provider execution, keep the same three frozen Phase 0 cases. Examine the stage artifact and diagnostic side by side for each C article:
1. Did a specific and genuinely interesting question survive from Reaction through final review?
2. Did the passage **show** evidence that changed the writer’s understanding rather than say “私は驚いた”?
3. Is the specific insight explained with a clear, intuitive counterexample/contrast?
4. Can an adult reader decide what to check next without internal labels leaking?
5. Is it engaging enough to publish, judged blind by the owner against the existing Elastic reference and the additional Forget-Only comparator?

Any C that is boring remains NO-GO even if all diagnostics and structural tests pass.


## Historical V3 evidence — recovered after first P3 CI run

Read-only inspected existing validated GitHub Actions artifact `editorial-engine-v3-phase0-checkpoint` from Run `39239644474` (no Gemini request). It records three completed C-only cases on `gemini-3.8-flash`:

| Historical case | Persona Article length (Unicode code points) | Fact-Safe length | Exact body equality |
| --- | ---: | ---: | --- |
| FFT criticism | 1,055 | 1,055 | Yes |
| Elastic Transformer | 898 | 898 | Yes |
| Claude × Google Workspace | 914 | 914 | Yes |

All three final bodies were already identical to Article Generation before Review. Thus, **Review did not create the flatness in these three actual samples.** The bottleneck is the Writer's move from planning artifacts to a reader-facing article, not merely the last safe-review stage. The previously recorded owner evaluation was C=27/60 versus A=46/60 and B=37/60.

An independent conservative surface-overlap replay of the historical stage texts found the Elastic question, evidence pivot, after-view, and discovery to be word-level **surface_present**, yet owner-judged editorial quality remained unsatisfactory. This falsifies using mere anchor phrase retention as a proxy for interestingness. In contrast, FFT lacked lexical overlap with parts of after-view/discovery and Claude lacked parts of evidence-pivot/after-view; these are **possible-loss signals only**, not proof that the ideas are semantically absent.

Based on that observation P3 adds a short `READER_DISCOVERY_SCENE` directive **only to experimental C**, not to frozen A/B: make the Evidence-supported concrete contrast or mechanism comprehensible *before* reporting the conclusion, without invented illustrations, mechanical word quotas, or a new provider call.

This is an experiment, not quality proof. The next live C-only run uses a changed prompt fingerprint and therefore cannot reuse old C outputs as current proof. Three locked cases, provider budget, and manual human GO remain unchanged.
