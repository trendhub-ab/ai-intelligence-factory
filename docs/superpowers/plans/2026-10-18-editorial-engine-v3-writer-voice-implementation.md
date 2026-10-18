# Editorial Engine v3 Writer Voice & Layout Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make V3 C articles naturally interesting in an evidence-led, first-person, 17-year-old Writer voice with gender-neutral Japanese, and fail closed on unreadable article formatting while preserving frozen A/B and every Production boundary.

**Architecture:** Change only the isolated Phase 0 C editorial prompts, not the shared frozen B baseline. Keep five inspectable C stages in one JSON response and one logical provider call per case; require the reader-visible Writer reaction, specific question, evidence-driven change of mind, discovery, and non-gendered language in both stage and bundled prompts. Add a deterministic Markdown/layout gate at the bundle boundary, resume boundary, and structural-proof boundary; leave subjective quality to human blind evaluation.

**Tech Stack:** Python 3.11, pytest 8.4.2 in locked CI, GitHub Actions, existing `google-genai` client only for separately approved manual live proof.

**Spec:** `docs/superpowers/specs/2026-10-17-editorial-engine-v3-reaction-first-design.md` (Writer Voice and gender-neutral revisions committed on 2026-10-18).

## Global Constraints

- **Isolation:** Only `experiments/editorial_engine_v3_phase0/`, its focused tests, and experiment-only validation may change. V1, Production Writer, Fresh/Daily, Evidence/Fact/Publication gates, Notion, and note delivery are untouchable.
- **Frozen comparators:** `A_CURRENT_WRITER` and `B_PERSONA_ONLY` output bytes, underlying `READY_CASES`, input digests, and blind mapping policy must not change. Do not silently change B's existing `PERSONA` prompt by improving C.
- **Budget:** Exactly one logical C provider call per case, three across the frozen cases; no new stage call, no Lite model, no model switching after the first success. 429/503 handling, checkpoint provenance, and cost counters remain auditable.
- **Voice:** First-person `私` and a Writer-owned theme-specific question are mandatory in reader-visible C prose; the Japanese itself must not signal gender. Youth vocabulary is optional and natural, not banned or injected by quota. No invented school life, direct product use, numbers, causes, or background facts.
- **Editorial integrity:** All five existing stage keys stay unchanged. The Article stage is responsible for lively prose; Fact-Safe Review validates every factual assertion before preserving or minimally correcting it. No hard-coded article template across cases.
- **Human acceptance:** Automated tests may certify contracts and formatting, **never** "interesting enough" or "gender-neutral enough" as a final editorial GO. A blind human read and note-publishability decision are mandatory.
- **API/merge gate:** Zero external provider calls in TDD or regular push. Any Gemini rerun is a *separate explicit approval* and must be after **17:00 JST**; **no merge** without a fresh `マージゴー`.
- **CI:** Keep the Phase 0 workflow's `push → contract` and `workflow_dispatch + run_live=true → live-proof` separation. No Production/CI workflow trigger should invoke Gemini on normal pushes.

## Review Focus

Five high-risk conditions and their test owners:

1. **Shared B/C Persona regression:** updating C must not change B prompt bytes or A/B comparison outputs → Task 1 `test_persona_only_baseline_stays_byte_frozen`; Task 3's existing `test_c_only_refinement_reuses_a_b_records_five_stages_and_spends_three_calls`.
2. **Double-encoded newlines:** a JSON string containing visible `\n` in article prose must fail, while actual newlines and literal `\n` inside fenced/inline code remain valid → Task 2 `test_article_layout_rejects_literal_escape_only_in_prose`.
3. **Visually broken article:** whitespace-only title, body-less headline, or free text without title must fail before blind delivery → Task 2 `test_article_layout_rejects_missing_heading_or_body`.
4. **Old or corrupted C checkpoint:** a same-fingerprint completed C with malformed text must not be reused or silently cause an unapproved extra provider replay → Task 3 `test_invalid_completed_c_resume_is_fail_closed_without_provider_call`.
5. **Synthetic first person / biased gender coding / unsupported exuberance:** lexical counts and pronoun presence cannot prove a credible Writer or permitted facts → Task 1 `test_c_voice_contract_keeps_gender_neutral_first_person_and_evidence_boundary`; final human rubric. Do not implement a brittle gendered-word blacklist as the sole quality validator.

---

### Task 1: Separate Frozen Persona B from Lively Gender-Neutral C

**Files:**
- Modify: `experiments/editorial_engine_v3_phase0/prompts.py`
- Test: `tests/test_editorial_engine_v3_phase0.py`
- Test: `tests/test_editorial_engine_v3_phase0_quality_contract.py`

**Interfaces:**
- Consumes: unchanged `Phase0Case`, `PERSONA` (the frozen B-specific legacy text), `_evidence_block(case: Phase0Case) -> str`.
- Produces: new `C_EDITORIAL_PERSONA: str`; `build_editorial_stage_prompts(case: Phase0Case) -> dict[str, str]` and `build_editorial_bundle_prompt(case: Phase0Case) -> str` use it, while `build_persona_only_prompt(case: Phase0Case) -> str` continues using unmodified `PERSONA`.

- [ ] **Step 1: Add RED tests for prompt isolation and C voice.**

  In `tests/test_editorial_engine_v3_phase0.py`, add `test_persona_only_baseline_stays_byte_frozen`: compare the complete B prompt for `_case("persona")` against the pre-change SHA-256 `49131f6f19b1df3d183610573cfc2806a26e8096bb2b2a07dbb166425865c315` (derived from the current branch's unmodified `PERSONA` and `_evidence_block`). Assert that the B prompt includes the legacy `若者言葉、過剰な感嘆符、絵文字、架空の実体験は使わない` sentence and contains none of C's new neutral-voice instructions. Keep the golden digest immutable; compute it only from the **pre-change** branch, not from the changed implementation.

  ```python
  assert hashlib.sha256(
      build_persona_only_prompt(_case("persona")).encode("utf-8")
  ).hexdigest() == "49131f6f19b1df3d183610573cfc2806a26e8096bb2b2a07dbb166425865c315"
  ```

  In `tests/test_editorial_engine_v3_phase0_quality_contract.py`, add `test_c_voice_contract_keeps_gender_neutral_first_person_and_evidence_boundary` for both the `Persona Article Generation` stage and the one-call bundle: assert `17歳`, `一人称`, `中性的`, `素朴な疑問`, `若者言葉`, `Writer Question`, `Evidence / Facts / Sources`, `架空` are present in the *intended, non-contradictory* guidance. Assert C no longer says `若者言葉は禁止` or `一人称単数は自然なら使ってよいが`. Assert C protects both feminine-coded and masculine-coded endings but does not demand a fixed slang list or a particular emotional outline.

- [ ] **Step 2: Run RED.**

  Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0.py::test_persona_only_baseline_stays_byte_frozen tests/test_editorial_engine_v3_phase0_quality_contract.py::test_c_voice_contract_keeps_gender_neutral_first_person_and_evidence_boundary`  
  Expected: the new C-quality test fails on the old C voice contract. The baseline B digest test should already pass.

- [ ] **Step 3: Implement only the C prompt contract.**

  Keep the original `PERSONA` literal, `build_persona_only_prompt`, and `_evidence_block` byte-for-byte unchanged. Define `C_EDITORIAL_PERSONA` separately in `prompts.py`. Switch C stage and bundle constructors to `C_EDITORIAL_PERSONA`, including Writer Reaction and Cognitive Shift, without touching B. Require a visible natural `私` reaction, question, evidence pivot and discovery; frame female/17-year-old as invisible character backstory and Japanese as gender-neutral. Permit `え、`, `なんで？`, and context-appropriate youth language; prohibit feminine/masculine caricature and fabricated personal experience. In *both* C article instructions require meaningful title, paragraph breaks, actual newline characters in JSON strings after decoding, and gender-neutral closing questions. Preserve all strict Fact/decision/Action and stage-label constraints.

- [ ] **Step 4: Run GREEN and focused existing contracts.**

  Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0.py tests/test_editorial_engine_v3_phase0_quality_contract.py`  
  Expected: 0 failures; B golden SHA unchanged.

- [ ] **Step 5: Commit the bounded prompt change.**

  `git add experiments/editorial_engine_v3_phase0/prompts.py tests/test_editorial_engine_v3_phase0.py tests/test_editorial_engine_v3_phase0_quality_contract.py`  
  `git commit -m "feat(v3): isolate frozen B and require neutral lively C Writer voice"`

### Task 2: Fail Closed on Article Layout at the Single-Call Boundary

**Files:**
- Modify: `experiments/editorial_engine_v3_phase0/contract.py`
- Modify: `experiments/editorial_engine_v3_phase0/live.py`
- Test: `tests/test_editorial_engine_v3_phase0_live.py`

**Interfaces:**
- Consumes: existing `EDITORIAL_STAGES` and `_parse_editorial_bundle(text: str) -> tuple[str, dict[str, str]]`.
- Produces: `validate_article_layout(article: str) -> None` in `contract.py`, raising `ValueError("invalid article layout: ...")` for malformed final text; `_parse_editorial_bundle` translates that to `RuntimeError("invalid editorial bundle: ...")`. The validator is shared by Task 3.

- [ ] **Step 1: Add RED layout tests with real JSON serialization.**

  Add `test_article_layout_rejects_literal_escape_only_in_prose`: build a five-stage JSON bundle via `json.dumps(..., ensure_ascii=False)`; set draft or final to a proper title plus *literal* `\n` characters (double escaped in the Python test input), assert rejection; replace them with genuine newline characters, assert success. Verify a fenced or inline code example containing a literal `\n` is not mistaken for an escaped article paragraph.

  Add `test_article_layout_rejects_missing_heading_or_body`: parameterize `"本文のみ"`, `"# \n\n本文"`, and `"# 題名"`; each fails at parse. A valid `"# 題名\n\n本文です。"` succeeds. Assert validation checks **both** `Persona Article Generation` and `Fact-Safe Review`.

  ```python
  with pytest.raises(RuntimeError, match="invalid editorial bundle"):
      live._parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))
  ```

  Update the existing `_reaction_first_payload` and mock C outputs to valid Markdown with a `# ` title and body. Update assertions in `test_editorial_bundle_requires_all_five_stages_and_uses_fact_safe_review_as_final` and C-only tests to their new literal expected Markdown; preserve all existing model-budget, fallback, checkpoint, and stale-fingerprint assertions.

- [ ] **Step 2: Run RED.**

  Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0_live.py -k "article_layout"`  
  Expected: layout tests fail because no validator yet exists.

- [ ] **Step 3: Implement the small deterministic validator.**

  In `contract.py` implement `validate_article_layout(article: str) -> None`: require a non-empty first Markdown H1 (`# title`) and at least one non-empty prose/body paragraph, with valid real line breaks. Reject visible escaped newline tokens in **prose outside Markdown inline-code/fenced-code regions**; do not replace raw `\n` by newlines or silently repair bad material. In `live._parse_editorial_bundle` validate both article stage strings after JSON parsing, before any C output is checkpointed/blind-packaged. Do not infer author gender or reading interest from a brittle regex. Preserve stage keys, JSON semantics, and one provider call.

- [ ] **Step 4: Run GREEN and existing live resilience tests.**

  Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0_live.py`  
  Expected: 0 failures, including old 429/503 locking and one-call budget tests.

- [ ] **Step 5: Commit.**

  `git add experiments/editorial_engine_v3_phase0/contract.py experiments/editorial_engine_v3_phase0/live.py tests/test_editorial_engine_v3_phase0_live.py`  
  `git commit -m "fix(v3): fail closed on broken generated article layouts"`

### Task 3: Preserve Resume/Proof Integrity and the Three-Call Boundary

**Files:**
- Modify: `experiments/editorial_engine_v3_phase0/live.py`
- Modify: `experiments/editorial_engine_v3_phase0/proof.py`
- Test: `tests/test_editorial_engine_v3_phase0_live.py`
- Test: `tests/test_editorial_engine_v3_phase0_proof.py`

**Interfaces:**
- Consumes: Task 2's `validate_article_layout(article: str) -> None`; existing `_valid_completed_c_case(case: dict[str, Any]) -> bool` and `evaluate_c_only_proof(output_dir: str | Path, *, model_candidates: Iterable[str] | None = None) -> dict[str, Any]`.
- Produces: the same public return shapes, plus explicit proof check `c_articles_layout_valid: bool`. No case, variant, stage, fingerprint-schema, or blinded label change.

- [ ] **Step 1: Add RED checkpoint/proof tests.**

  `test_invalid_completed_c_resume_is_fail_closed_without_provider_call`: take a completed C checkpoint bearing the **current** refinement fingerprint and an old C body with visible escaped `\n` or missing title. Attempt resume with a client that records provider calls; assert a clear `RuntimeError`, **zero** provider calls, untouched A/B bytes, and no invalid C in human-facing blind artifacts. Do not silently reset cumulative cost and rerun a same-fingerprint invalid C.

  `test_c_only_structural_proof_rejects_unreadable_c_article`: construct a complete current C proof fixture and mutate one C draft or final to malformed layout while keeping A/B untouched. Assert the exact failed proof fields:

  ```python
  assert report["status"] == "FAIL"
  assert report["checks"]["c_articles_layout_valid"] is False
  ```

  Change the existing `_complete_current_refinement` proof fixture's C draft/final placeholders into valid titled Markdown. Update other C-only mock C strings likewise, without changing assertions about preserved A/B or exact three logical calls.

- [ ] **Step 2: Run RED.**

  Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0_live.py::test_invalid_completed_c_resume_is_fail_closed_without_provider_call tests/test_editorial_engine_v3_phase0_proof.py::test_c_only_structural_proof_rejects_unreadable_c_article`  
  Expected: both fail against existing reuse/proof behavior.

- [ ] **Step 3: Close the checkpoint and proof gaps.**

  Extend `live._valid_completed_c_case` to reject layout-invalid draft/final. In `_run_c_only_refinement`, when the current fingerprint matches but declared completed C is layout-invalid, fail closed before requesting a provider call; a **new explicitly authorized iteration** may regenerate under a changed fingerprint, not as an accidental same-run retry. Keep the existing changed-fingerprint scrub behavior and exact cumulative counters. In `proof.evaluate_c_only_proof`, validate every completed C draft and final with the shared validator and add `c_articles_layout_valid` to `checks`. Structural PASS remains **not** a human-interest GO.

- [ ] **Step 4: Run GREEN with proof and C-only regressions.**

  Run: `python -m pytest -q tests/test_editorial_engine_v3_phase0_live.py tests/test_editorial_engine_v3_phase0_proof.py`  
  Expected: 0 failures; existing `ab_byte_identical`, `current_fingerprint`, three-call limit, artifact freshness, no Lite, and locked-model tests remain green.

- [ ] **Step 5: Commit.**

  `git add experiments/editorial_engine_v3_phase0/live.py experiments/editorial_engine_v3_phase0/proof.py tests/test_editorial_engine_v3_phase0_live.py tests/test_editorial_engine_v3_phase0_proof.py`  
  `git commit -m "test(v3): guard stale C resumes and proof article layout"`

## Offline Regression and CI Gate (before any new live proof)

Perform all steps on `feature/editorial-engine-v3-phase0` in its isolated worktree; do not merge or rebase onto Production as part of this plan.

- [ ] `python -m compileall -q experiments/editorial_engine_v3_phase0 tests` — expected exit 0.
- [ ] `python -m pytest -q tests/test_editorial_engine_v3_phase0.py tests/test_editorial_engine_v3_phase0_live.py tests/test_editorial_engine_v3_phase0_quality_contract.py tests/test_editorial_engine_v3_phase0_proof.py` — 0 failures.
- [ ] `GEMINI_PERSISTENT_DAILY_COUNTER=false python -m pytest -q tests` — full offline repository regression, 0 failures. Install the CI-pinned Python dependencies first; do not run live generation from tests.
- [ ] `python integration_stability_guard.py` — expected exit 0, no forbidden Production imports/changes.
- [ ] `python regression_suite.py --self-test`, then `python regression_suite.py --bootstrap --full` — both exit 0, no live providers.
- [ ] Inspect `git diff --name-only` and `git diff --check`: changed paths only in the experimental surface and its tests; no Production/V1 code, frozen case, baseline or normal-push live trigger changes.
- [ ] Wait for `Editorial Engine v3 Phase 0 / Phase 0 contract tests` on the Draft PR head; record its actual status. If executing full GitHub CI with the feature branch as ref, dispatch **Synthetic Regression Suite** `suite=full` (zero-provider); do not dispatch `Real Article Regression Test`, which invokes Production/provider APIs.
- [ ] Document offline RED→GREEN and CI evidence on PR #810. If a test fails, stop, diagnose, and repair in the same experimental scope; do not claim CI success from planned commands.

## Human Reading and Live Proof Handoff (not authorized by this plan)

- Baseline C-only run: `39115310334`, prior blind C total **27/60**, versus A **46/60** and B **37/60**; the historical evaluation is immutable. The ChatGPT-authored Elastic Transformer sample is an **editorial north star**, not a recovered full-text golden fixture or automatic test oracle.
- After **verified offline PASS and relevant CI PASS**, seek **separate permission** to run a bounded **C-only `workflow_dispatch` with `run_live=true` and `regenerate_c_only=true`**, no earlier than **17:00 JST**. Use prior checkpoint/artifact only after verifying that the 7-day-retained artifact is still present and that frozen A/B and input digests match; if expired/mismatched, stop and ask for a new approved baseline strategy. Never manufacture or silently rebuild A/B.
- Keep exactly three logical C calls, one locked non-Lite model, all five stages. Inspect where the writer voice survives from `Persona Article Generation` to `Fact-Safe Review`. A proof `PASS` certifies structural integrity only.
- Blind review must score the previously locked four axes (last-page motivation, opening hook, memorability, AI smell), additionally note **gender-coded phrasing**, fake lived experience, evidence fidelity, and note-publishability. Lock all three case scores **before** looking at X/Y/Z mappings. Compare actual reading enjoyment with the sample; do not use a mandatory slang count or pretend automated scores replace the owner.
- Experiment remains `DRAFT / NO-GO` unless the owner explicitly judges the new articles interesting and suitable for note. A future merge requires a new explicit `マージゴー` after verification.

## Plan Self-Review

- **Spec coverage:** Writer Reaction, Editorial Discovery, Cognitive Shift, article voice, minimal Fact-Safe Review, Evidence boundary, layout, anti-template, format fail-closed, frozen inputs/A-B, C-only budget, human GO are mapped to the above tasks and final gate.
- **Boundary:** No changes to Production, V1, case data, dispatch behavior, provider budget, or blind mapping. B's shared Persona is explicitly separated; this is critical to comparator integrity.
- **No hidden API:** Every implementation task is offline TDD; the only live workflow remains a future human-authorized step.
- **Human vs machine:** Layout and stage contracts are deterministic; natural gender neutrality and "fun to read" require human reading rather than false confidence from keyword filters.