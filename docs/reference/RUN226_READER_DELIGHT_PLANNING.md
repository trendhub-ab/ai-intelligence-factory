# Run226 — Reader Delight Planning

## Purpose

Run226 improves only the free note article's human editorial quality: relatability, readability, intellectual entertainment, and article-specific point of view. It does not change Screening, Evidence collection, Decision Score, Notion product logic, API budget, note publication automation, or public-release policy.

The external editorial review that motivated this Run correctly identified the main opportunity: human-ness should not be pasted onto a finished technical report. Reader experience should influence how verified Evidence is ordered and explained from the start.

## Adopted editorial principle

Before drafting, the existing article-generation request silently plans five lenses from the verified SOURCE BOUNDARY:

1. **Reader Tension** — the reader's real question or friction.
2. **Discovery** — the article-specific point that can produce an “I see” moment rather than a press-release summary.
3. **Concrete Consequence** — what changes for work, choice, usage, or adoption, but only to the extent directly supportable by Evidence.
4. **Explanation Bridge** — the explanation order that lets a non-engineer reach the technical core; analogy/question/scene/conversation are optional tools, not requirements.
5. **Editorial Point of View** — the Evidence-bounded editorial judgment that should naturally shape the article rather than appear as a pasted final sentence.

These are internal planning lenses, not five visible sections and not a fixed order.

## What Run226 deliberately rejects

Run226 does **not** turn the Claude review's quantitative style suggestions into hard publication templates. In particular, it does not require or evenly distribute:

- a fixed number of sentences per paragraph;
- a fixed number of one-sentence paragraphs;
- one or two reader questions;
- a maximum number of bullet lists as a new Hard Gate;
- a mandatory analogy;
- a mandatory conversational marker;
- a fixed hook taxonomy such as problem / number / contrarian / practical;
- equal use of hook types across recent articles;
- a fixed position for Decision Voice.

Those can be useful diagnostics in context, but hard quotas would create a new “human-looking AI template,” defeating the objective. Existing Reader Experience / Human Appeal diagnostics remain authoritative.

## Evidence boundary

Reader Delight never outranks factual integrity.

Run226 explicitly prohibits inventing, for explanatory convenience:

- numeric baselines, transformed times, costs, counts, or dates;
- people, conversations, quotes, usage scenes, or anecdotes presented as factual;
- adoption numbers, trend claims, competitor roadmaps, causal claims, or majority-belief claims;
- concrete conversions of a source multiplier/percentage when the baseline and converted value are not both supported in the SOURCE BOUNDARY.

A ratio such as “10x” must not become “8 hours becomes 45 minutes” merely because the latter is easier to picture. If the source does not contain the relevant baseline, the article must explain the implication without manufacturing one.

Analogies are explanatory bridges only. They cannot replace the technical mechanism or be treated as Evidence.

## Integration

`run226_reader_delight_planning.py` wraps the existing `pipeline.build_decision_prompt` at Production runtime. It appends the planning contract exactly once and preserves the base prompt unchanged.

`production_pipeline.py` installs Run226 after the existing Fact / technical-claim / scope / funnel layers and before downstream Reader Value / Publication processing.

Because this changes the editorial generation policy, `run226_reader_delight_planning.py` is included in `publication_contract.PUBLICATION_POLICY_FILES`. A manuscript stamped under an older policy therefore remains fail-closed until reconciled under the current policy.

## Invariants

- Existing SOURCE BOUNDARY and Evidence-to-Decision rules remain unchanged.
- Existing Run126–Run144 Reader Experience behavior remains valid.
- Run223 / Run224 technical-claim precision is not weakened.
- Existing Human Appeal and Publication gates are not relaxed.
- No new Gemini/model call site is added; Run226 uses the already-existing article-generation call only.
- No Notion schema or paid-member product behavior changes.
- Daily remains PAUSED.
- note public release remains human-only; automation stops at private draft.

## Regression requirements

Run226 tests prove that:

- all five planning lenses are present;
- invented explanatory specificity is explicitly prohibited;
- style counts are not converted into new hard quotas;
- the original article prompt is a strict prefix of the augmented prompt;
- augmentation and installation are idempotent;
- no new `_generate_via_chat` / `genai.Client` call site is introduced;
- Production runtime installs Run226;
- Publication policy fingerprint includes Run226;
- the canonical Production specification documents the same contract.

Full repository CI and existing Reader Delight regressions must pass before merge.
