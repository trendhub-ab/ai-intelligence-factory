# Editorial Engine v3 Reaction-First Redesign

**Status:** Design approved in chat; implementation not started  
**Date:** 2026-10-17  
**Branch:** `feature/editorial-engine-v3-phase0`  
**Production main:** unchanged  
**Parent direction:** `AIIF_Writer_Editorial_大改修方針仕様書_v3_2026-10-15-1.md`

## 1. Purpose

Rebuild the AIIF article-generation flow so that the article is not merely an organized explanation of verified facts, but a readable experience in which a distinct writer reacts to a piece of AI news, questions it, checks the evidence, changes her understanding, discovers the deeper point, imagines what could change next, and then connects that discovery to an adult business reader's decision.

The target Writer Persona remains the approved direction:

- an AI-excited 17-year-old high-school girl;
- not represented through slang, caricature, exaggerated punctuation, emoji, or fictional school-life anecdotes;
- represented through freshness of perception, curiosity, honest questions, emotional response, future imagination, and visible cognitive change;
- facts remain cold and auditable; expression may be lively and personal.

The redesign exists because the first Phase 0 implementation produced articles that were factually clean but editorially flat. The generated output repeatedly regressed into polished business explainer prose. That is a failure against the approved specification even when it outperforms the current Writer.

## 2. Problem statement

The previous Phase 0 flow was:

```text
Evidence
→ Editorial Discovery
→ Persona Narrative
→ Article Writing
→ Editorial Review
```

The structure was conceptually correct but operationally wrong in three ways.

### 2.1 Persona was treated as a constraint, not an active source of perception

The prompts strongly prohibited slang, acting, exaggeration, and invented experience, but did not equally require the writer's own reaction, question, emotional movement, or future imagination to survive into the published prose.

This caused safe language such as:

- “抱くべき素朴な疑問があります”
- “疑いたくなるのが自然な感覚です”
- “素朴な疑問かもしれません”

These phrases contain a question but no identifiable thinker.

### 2.2 Article Writing normalized the narrative

Even when Persona Narrative contained useful first-person curiosity and cognitive change, Article Writing tended to convert that material into neutral business prose.

The model optimized for “complete article” rather than “preserve the writer's lived intellectual movement.”

### 2.3 Editorial Review rewrote instead of protecting

Editorial Review behaved like a polishing layer. It improved structure and business readability but often removed precisely the irregular, personal, exploratory signals that made the article interesting.

This violated the intended separation:

- Writer creates the reading experience.
- Review protects Fact, Evidence, decision integrity, and publication safety.

## 3. Design decision

Adopt a Reaction-First Editorial Engine.

```text
Evidence
↓
Writer Reaction
↓
Editorial Discovery
↓
Cognitive Shift
↓
Persona Article Generation
↓
Fact-Safe Review
```

This is a structural redesign, not a prompt patch.

## 4. Core principle

The engine must not begin by asking for an article.

It must first ask what this writer genuinely notices, wonders, doubts, fears, hopes for, or imagines when seeing the evidence.

The system then uses evidence to move that perception.

The published article should feel as if a human writer actually encountered the news and thought through it, rather than as if the conclusion existed before the article began.

The output principle is:

> Intelligence stays cold. The prose is allowed to feel alive.

## 5. Stage contracts

### 5.1 Evidence

No Persona is applied.

Input remains limited to existing Phase 0 canonical fields:

- source
- evidence
- facts
- verified numbers
- technical conditions
- existing decision
- action
- target reader

No new external Fact may be introduced by later stages.

### 5.2 Writer Reaction

This is a new first-class editorial artifact.

The model must not write article prose yet.

It must produce theme-specific answers to questions such as:

- What did I react to first?
- What made me genuinely curious?
- What did I not immediately understand?
- What felt too good, too strange, too scary, or too consequential to accept at face value?
- If this became normal, what future change immediately comes to mind?
- What would an adult expert possibly skip over that I would still want explained?

The output must be specific to the evidence. Generic enthusiasm about AI is a failure.

Required concepts:

- `Reaction`
- `Curiosity`
- `Question`
- `Future Imagination`

Not every article needs the same emotional type or intensity.

### 5.3 Editorial Discovery

Discovery begins from the tension between Writer Reaction and Evidence.

It must identify:

- `Surface`: what the news appears to be about;
- `Interesting Tension`: why the writer's first reaction may be incomplete;
- `Evidence Pivot`: which evidence changes or sharpens the initial view;
- `Deeper Insight`: the meaning one level below the headline;
- `Editorial Thesis`: what the article is really about.

Discovery must not manufacture drama. If the evidence confirms the writer's first excitement, the cognitive movement can be “expected → even more interesting.”

### 5.4 Cognitive Shift

This stage replaces the old generic Persona Narrative contract.

It explicitly records how the writer's understanding moves.

The shift is not required to follow a fixed emotional curve.

Examples of valid movement include:

```text
confusion → understanding
```

```text
skepticism → surprise
```

```text
excitement → concern
```

```text
small feature → large future implication
```

```text
expected benefit → different, deeper benefit
```

Required fields:

- `Before View`
- `Evidence Encounter`
- `After View`
- `What I Now Find Interesting`

The stage must include a theme-specific movement. Reusing the same emotional structure across cases is a failure.

### 5.5 Persona Article Generation

This is the only stage that writes the full article.

The article must preserve the Reaction and Cognitive Shift as part of the reading experience instead of treating them as invisible planning notes.

The writer is allowed to use first person when natural.

The article does **not** need to literally use every planning label or repeat the planning artifact verbatim.

However, the final prose must contain observable equivalents of multiple Persona signals appropriate to the theme:

- writer's own reaction;
- writer's own question;
- a visible change in understanding caused by evidence;
- a clearly articulated discovery of what is truly interesting;
- future imagination or human implication when supported by the evidence;
- connection from that discovery to the adult reader's decision.

The prose must not hide the writer behind generic phrases such as “we should consider” or “one might wonder” when a personal reaction is the intended source of the point.

The article must still be written for adult business readers.

The Persona changes the lens, not the audience.

### 5.6 Fact-Safe Review

The review stage changes role fundamentally.

It is not a rewrite pass.

Default behavior: **preserve the article unchanged** unless a concrete defect is found.

The reviewer checks only:

- unsupported external Fact;
- changed or invented numbers;
- changed named entities;
- Evidence contradiction;
- decision/action distortion;
- unsupported certainty;
- Persona caricature or fabricated experience;
- repeated narrative template;
- obvious AI boilerplate that can be removed without flattening the writer.

If a defect exists, perform the smallest local edit necessary.

The review must not:

- convert first person into impersonal prose merely for formality;
- remove the writer's curiosity because it is subjective;
- replace a specific question with generic business language;
- restructure the whole article for neatness;
- make every article follow the same title/introduction/conclusion formula;
- erase future imagination when it is framed as a question or implication rather than a fact claim.

## 6. Persona policy

### Required

The Writer Persona must appear through:

- fresh surprise;
- curiosity;
- willingness to ask basic questions;
- healthy skepticism;
- future imagination;
- emotional reaction to evidence;
- willingness to revise an initial view;
- an identifiable point of view.

### Prohibited

The following remain prohibited:

- “やばい”, “神”, “めっちゃ”, or forced youth slang;
- fake school anecdotes;
- fake friends, teachers, classes, or personal product use;
- emoji as a Persona substitute;
- exaggerated claims;
- unsupported future predictions;
- facts created only to make the story more dramatic.

## 7. Emotion intensity

Emotion is adaptive, not fixed.

The system should expose an explicit editorial planning value such as:

```text
Emotion Intensity: LOW | MEDIUM | HIGH
```

or an equivalent bounded representation.

The value is selected from the theme and evidence, not from a fixed article template.

Examples:

- technical breakthrough with strong evidence: medium/high curiosity;
- safety/risk finding: concern or unease may dominate;
- incremental product update: lighter curiosity;
- ambiguous or weak evidence: restrained skepticism.

Emotion must be a reaction to evidence, never a replacement for evidence.

## 8. Quality gates

Phase 0 must be evaluated against the canonical specification as an absolute standard, not merely against current Writer A.

A candidate article fails if any mandatory condition below is materially absent.

### 8.1 Editorial Persona Gate

For each article, reviewers must be able to identify:

1. a real Writer presence;
2. an initial Reaction;
3. a Writer-owned Question or curiosity;
4. a change or sharpening of understanding due to Evidence;
5. what the Writer ultimately finds most interesting;
6. future imagination or human implication when appropriate;
7. a theme-specific emotional/cognitive path.

These signals need not appear as labeled sections or formulaic sentences.

### 8.2 Interest Gate

The article must be genuinely enjoyable or compelling to read, not merely correct.

Human evaluation asks:

- Would I continue after the opening?
- Is there a moment of discovery?
- Did the article make me see the news differently?
- Does anything stick in memory?
- Does the article sound like someone actually thought about the news?

### 8.3 Evidence / Fact Gate

Existing fail-closed Fact and Evidence protections remain unchanged.

No Persona improvement can compensate for unsupported facts.

### 8.4 Anti-template Gate

Across the three Phase 0 cases:

- emotional curves must differ where the evidence differs;
- openings must not reuse the same pattern;
- headings must not mechanically repeat the same sequence;
- the same “すごい→でも待って” structure must not appear by default.

### 8.5 User Acceptance Gate

The experiment is not GO merely because automated tests pass or C beats A.

The owner must actually read the generated articles and judge that they are interesting enough to publish on note.

If the owner says all three are boring, the Phase 0 result is NO-GO regardless of relative scores.

## 9. Phase 0 experiment design

Keep the existing three historical Ready cases:

1. FFT criticism / risk
2. Elastic Transformer technical breakthrough
3. Claude × Google Workspace product update

Inputs remain frozen:

- same Evidence;
- same Facts;
- same Source;
- same Target Reader.

Use the existing non-Lite model constraints and run-level model locking.

For iteration efficiency, A/B may remain frozen while only C is regenerated when the underlying Evidence and comparator text are unchanged.

C-only refinement remains bounded to one logical provider call per case unless the implementation plan explicitly changes that budget.

## 10. Required output artifacts

For each C case, retain inspectable stage outputs:

- Writer Reaction
- Editorial Discovery
- Cognitive Shift
- Persona Article Generation
- Fact-Safe Review result

The artifact must allow reviewers to identify exactly where Persona or interest was lost if the final article is weak.

The blind package should expose only final candidate articles; stage artifacts remain separate diagnostic evidence.

## 11. Fail-closed rules

The experiment must fail closed if:

- any required stage output is missing or empty;
- the final article is empty;
- external facts are introduced;
- a Lite model is selected;
- resume data does not match immutable case inputs;
- C-only refinement cannot prove that A/B comparators came from the expected checkpoint;
- Persona quality checks collapse to simple keyword matching as the sole GO criterion.

Automated tests may assert structural contracts, but final Persona/interest judgment remains Human Evaluation.

## 12. Scope boundaries

This redesign is still Phase 0 experimental code.

It does **not** yet change:

- Production Writer;
- Fresh;
- Daily;
- Notion write path;
- note draft creation;
- Technology Intelligence;
- Decision History;
- Evidence collection;
- Fact Gate;
- Publication Gate production thresholds.

No merge to `main` is permitted until the redesigned Phase 0 passes the approved experiment gate and the owner explicitly authorizes integration.

## 13. Implementation direction

The implementation should favor explicit typed/structured stage contracts over one large ambiguous prompt.

However, provider-call count must remain cost-conscious. A single provider call may return multiple structured editorial artifacts if and only if the model output preserves the semantic stage boundaries and tests can verify the contract.

Do not introduce extra Gemini calls merely to make the architecture look modular.

The likely implementation touchpoints are limited to the experimental surface:

- `experiments/editorial_engine_v3_phase0/prompts.py`
- `experiments/editorial_engine_v3_phase0/contract.py`
- `experiments/editorial_engine_v3_phase0/live.py`
- focused Phase 0 tests
- Phase 0 workflow only if an input/artifact contract changes

Production code remains untouched.

## 14. Acceptance criteria before implementation is considered complete

1. Focused tests fail first for the new Reaction-first contracts.
2. Minimal implementation makes them pass.
3. Existing Phase 0 resilience tests remain green.
4. Normal push does not trigger Gemini live generation.
5. C-only replay remains available for cost-efficient human testing.
6. Generated C articles visibly contain theme-specific Writer presence, curiosity, cognitive movement, and discovery.
7. Evidence/Fact quality is not degraded.
8. The three articles do not share a mechanical emotional or structural template.
9. The owner reads the final articles and judges them materially interesting.
10. Only after that Human Evaluation may the experiment be marked GO.

## 15. Non-goals

This redesign does not attempt to:

- make the prose sound literally teenage;
- optimize SEO;
- redesign note eyecatch;
- change paid Decision Intelligence tone;
- alter decision scoring;
- regenerate existing Notion content;
- merge experimental architecture directly into Production.

## 16. Final design statement

The Reaction-First Editorial Engine is successful only when the reader can feel that someone encountered the news, cared about something specific, asked a real question, learned from evidence, changed or sharpened her view, and then handed that discovery to an adult reader without compromising factual integrity.

If the result is merely a polished business explainer, the system has failed even if it is accurate.
