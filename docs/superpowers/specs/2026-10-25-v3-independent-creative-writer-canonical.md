# AIIF V3 — Independent Creative Writer 正本設計（2026-10-25）

**Status:** OWNER-APPROVED DEVELOPMENT BASELINE / EXPERIMENT ONLY / NO PRODUCTION GO.
**Baseline main (restore point):** `4032060c6b9919ab2a05849e5607d666f503361f`.
**Selected historical P5 reference:** PR #852, `95016a65701979063f56130bf181bca831661f5d`. The 83/100 historical score (FFT 75, Elastic 85, Claude 88) was *subjective human editorial scoring with Gemini 3 Flash Preview*, not a reproducible production-quality guarantee.
**Decision:** Stop additive prompt patching as the primary strategy. Independently redesign *only* the Creative Writer boundary. Prior P5 experiments and draft PRs remain historical evidence, not implementation parents. This document supersedes their **future V3 writer-development direction only**; it does NOT overwrite production contracts, audits, or historical facts.

## 1. Why change direction

Observed recent isolated Elastic comparison: four A–D manuscripts were saved; editorial scores 60 / 47 / 55 / 51 out of 100 (single-sample subjective reading); E was incomplete after HTTP 504. Conditions and model variants were not matched across all arms; they cannot establish that integration caused the change from the historical Elastic 85. Also, the original-only new-model arm did not reproduce historical quality. Do not infer model/prompt/integration causality from cross-model or cross-era score changes.

Working hypotheses to falsify:
1. Model/transport/sampling changes explain part of the observed shift.
2. Five-stage JSON generation compresses curiosity into summaries during manuscript formation.
3. Management/Decision/Action/schema constraints in the creative prompt suppress independent narrative discovery.
4. Source fact packs may not contain the **why/how evidence** needed to answer the writer's own best question.

All four remain hypotheses. No new experimental writer can be declared superior before blinded source-matched evidence.

## 2. Immutable operational boundary: V1, V2 and Production

- **No edits** to V1/Classic, V2 Shadow, Daily workflows, provider quota/retry machinery, runtime state, Production pipeline, note/Notion sync, existing LocalSkills decisions, publication contracts or Evidence/Fact/Reader/Publication Gates in this phase.
- No Automatic dispatch, Gemini paid calls, new GitHub Actions workflow, note/Notion publish or artifact deliveries.
- The default production editorial style remains `classic`. Existing `v3_p5` remains validation-only; the new Writer is **not registered** in any production selector.
- Use a dedicated branch cut from the exact immutable main SHA above. Changes restricted to `docs/superpowers/specs/`, `docs/superpowers/plans/`, `experiments/v3_writer_independent.py`, and `tests/test_v3_writer_independent.py` in Phase 0.
- `MERGE GO` separately required; commit to branch or open DRAFT PR is NOT publication authorization.
- On any incident: stop experimental work; keep `main` + V1/V2 intact. To remove experimental work, close PR/stop using branch. For any future opt-in integration, rollback by reverting its isolated commit or disabling the explicit opt-in; `classic` is the default. Never force-reset main.
- Compare branch changes to baseline. In Phase 0 the list of changed files must be an exact subset of the allowlist above; **zero differences** are permitted for V1/V2/Production files.

## 3. Three explicitly separated responsibilities

**Research/Evidence:** Supply a fact pack with source URLs, atomically attributable claims, relevant conditions/limitations and — when verified — mechanism, tension and genuine unanswered questions. Management scores/Ready labels are NOT evidence. If a key why/how question lacks evidence, the writer must frame it as unknown; never invent the answer.

**Independent Creative Writer:** Receive only whitelisted evidence and the minimal voice brief. Output a single reader-facing Japanese Markdown article, NOT a five-key editor/Fact JSON, management metadata or publication flags. Preserve the *thinking stance*, not a performance of a teenage identity: a curious 17-year-old's fresh questions, neutral non-gendered conversational Japanese, real discovery through specific evidence, some warmth, no invented experiences or exaggerated claims. Do not require synthetic surprise, fixed question counts, templates, mandatory first-person/length quotas, or business-summary headings. Writer may not expand the factual boundary.

**Independent Fact & Editorial Review:** After a complete draft, separately inspect traceable claims, source conditions, factual errors and unsupported promises. Apply surgical corrections only; do not turn discovery into a bland summary. Reader appeal is independently judged by humans, not inferred from stage completeness or CI. Existing Production Evidence/Fact/Reader/Publication Gates remain authoritative on eventual opt-in integration. **This review is NOT implemented/approved in Phase 0**; a prompt builder does not make an article safe for publication.

## 4. Validation design and acceptance

A. **Provider-free contract proof (Phase 0):** Pure writer prompt builder accepts typed source facts and never accepts management input. No network/client/secrets/filesystem writes, no model calls, no production registration. Confirm source URLs/claim IDs, deterministic fingerprint, incomplete pack fail-closed, and source/production isolation tests.

B. **Diagnostic replay without generating new article:** Preserve historic original P5 samples and A–D encrypted originals PRIVATE; independent readers compare completed manuscripts, keeping arm/model identity hidden until scoring. Historical 83 points is an editorial reference, never a statistical target on another model.

C. **New matched live test (requires separate explicit owner GO):** Same source/qualifiers/fact pack, same model, transport, generation settings and sampling policy for baseline versus minimalist independent Writer. At least FFT/Elastic/Claude and ideally ≥3 independent outputs per arm; cap costs, honor canonical persistent quota and keep raw drafts private/encrypted. Pre-register versioned prompts and rubric; reviewers blinded to arm/model, record source fidelity and generation failures (no cherry-picking). Differing model comparisons must be labeled exploratory, not causal.

D. **Editorial rubric (100):** Opening 15; authentic specific curiosity 15; evidence-led discovery 20; change of understanding 15; natural Japanese 15; memorability 10; claim restraint 10. Review actual articles, not prompt compliance. Also track attempt cost, completion rate, human-acceptable article yield, and later opt-in audience engagement/conversion. An aspirational ≥90 score is not a sufficient production gate by itself.

E. **Promotion:** Only after reproducible blind improvement plus independent factual/claim review and unchanged Production gate proofs; separate owner MERGE GO, validation-only shadow, then explicit release GO. New writer must NEVER silently become `classic` or Ready. No changes to V1/V2 during promotion.

## 5. Explicit non-goals

No P5 E rerun as prerequisite. No pursuit of perfect CI scores at the expense of reader appeal. No new synthetic style-only gate that approves prose. No claim that a single historical Preview score can be replicated on 3.6/3.8 Flash. No unreviewed manuscript in repository, Actions logs/artifacts, Notion or note.

## 6. Records/links

- Historical baseline: PR #852; Run #39963513015.
- Comparative investigation: Run #40178724927, Run #40192146520 (504 E; partial encrypted handoff).
- Existing integration plan (reference only): `docs/superpowers/specs/2026-10-24-v3-p5-full-five-stage-one-shot.md`.
- This document and accompanying plan are the canonical **new-development decision**, not a Production status change.
