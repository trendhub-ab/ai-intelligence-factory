# Editorial Engine v3 Persona-Preservation Refinement Plan

> **Status:** Follow-up to Reaction-First C-only live proof Run `39025335459`; offline refinement only until RED→GREEN evidence is complete.

**Goal:** Prevent Persona Article Generation from flattening strong Reaction-First planning artifacts into generic business-explainer prose, while tightening the frozen Evidence/Fact boundary and preserving the five-stage / one-logical-call-per-case architecture.

**Observed live-proof failure:** Writer Reaction, Editorial Discovery, and Cognitive Shift were materially stronger and theme-specific, but all three final articles normalized writer-owned reaction/question/cognitive movement into generic explanatory language. Fact-Safe Review then preserved those flattened drafts and missed several broader/stronger-than-input assertions.

## Constraints

- Do not change A/B comparators.
- Do not change the three frozen Phase 0 cases.
- Do not add a sixth stage.
- Do not add Gemini calls; C remains one logical provider call per case.
- Do not touch Production Writer, Fresh, Daily, Notion/note paths, Evidence collection, Fact Gate, or Publication Gate.
- Do not turn Persona quality into a keyword-only automated GO gate; final quality remains human-evaluated.
- Do not run another paid/live C-only proof during this refinement unless separately authorized after offline GREEN.

## Task 1 — RED: require explicit Persona preservation contract

**Files:**
- Modify: `tests/test_editorial_engine_v3_phase0.py`

Add assertions that Persona Article Generation instructions explicitly require:

- one unmistakably writer-owned reaction anchor in the final prose;
- semantic preservation of the specific Writer Question;
- one visible Evidence-caused before→after cognitive movement;
- preservation of the theme-specific `What I Now Find Interesting` discovery;
- no substitution of writer ownership with generic collective voice or reader-directed rhetoric when those forms erase the original writer signal;
- explicit anti-flattening examples covering `私たちは〜`, `疑問が生じます`, and `〜ではないでしょうか` when used as replacements for writer-owned Reaction/Question/Shift.

Add Fact-Safe Review assertions requiring:

- every factual/background/causal assertion to stay inside frozen Evidence/Facts/Sources;
- true-but-unstated domain knowledge is still an external Fact and must be removed or reframed;
- stronger certainty than the input is a defect;
- new causal claims/generalizations are defects unless directly supported.

Run focused tests and confirm RED before implementation.

## Task 2 — GREEN: minimally harden Reaction-First prompts

**Files:**
- Modify: `experiments/editorial_engine_v3_phase0/prompts.py`

Strengthen both the individual Persona Article Generation prompt and the bundled one-call prompt so the model must carry forward, semantically rather than mechanically, at least these prior-stage anchors:

1. the Writer Reaction;
2. the Writer Question;
3. the Evidence-caused cognitive shift;
4. the final discovery / what the writer now finds interesting.

The final prose may remain natural Japanese and does not need labels. First-person singular is allowed but not mandatory if writer ownership is otherwise unmistakable.

Explicitly prohibit replacing those anchors with generic copy such as:

- `私たちは〜` as a substitute for the writer's own reaction;
- `疑問が生じます` / `関心が生じます` as a substitute for a specific writer-owned question;
- `〜ではないでしょうか` as a substitute for the writer's own discovery/question.

These phrases are not globally banned; they are forbidden only when they erase the Reaction-First ownership required by the stage contract.

Strengthen Fact-Safe Review so it compares factual assertions against the frozen input boundary and corrects/removes:

- unstated background knowledge;
- stronger-than-input certainty;
- unsupported causal language;
- generalized claims not present in Evidence/Facts/Sources.

Keep review unchanged-by-default for articles without a concrete defect.

## Task 3 — Verification

Run:

`python -m pytest -q tests/test_editorial_engine_v3_phase0.py tests/test_editorial_engine_v3_phase0_live.py`

Expected: GREEN with the existing 5-stage parser, C-only budget, checkpoint provenance, and normal-push live skip unchanged.

Verify normal push still skips Gemini live generation.

Do not run a second live C-only proof in this task. Record the branch as **offline-ready / live-unproven**, with Phase 0 still **NO-GO** until a later bounded three-call proof and owner human evaluation.