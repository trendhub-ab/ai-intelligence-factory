# V3 P5 Golden Editorial Regression Contract (Draft, 2026-10-24)

**Status:** DRAFT / no Production adoption / no merge without owner MERGE GO.
**Original selected baseline:** PR #852, `95016a65701979063f56130bf181bca831661f5d`.
**Historical proof:** run [39963513015](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/39963513015), artifact `12506417026`.
**Historical HUMAN ratings:** FFT 75 / Elastic 85 / Claude 88, mean 83/100. These are NOT Fact/Publication approval, and they use the now-excluded `gemini-3-flash-preview` model.

## Non-negotiable editorial objective

P5 Writer is an intellectually curious 17-year-old, but **does not perform age or gender**. Natural neutral Japanese, theme-specific naïve questions, surprise grounded in Evidence, a visible change of understanding, and reader discovery are the goal. Do not substitute fake memories, exclamations, repeated rhetorical questions, `私は驚いた`, generic advice, or corporate/consultant summaries.

The original five-stage deliverables are **Writer Reaction → Editorial Discovery → Cognitive Shift → Persona Article Generation → Fact-Safe Review**. Article Generation must carry forward the Writer's actual concrete question and reveal *why the evidence changed the view*. Fact-Safe Review may repair only fact/claim inaccuracies, never sand away a supported authorial discovery as mere style. Structural completeness alone does not prove either behavior.

## Pinned assets and reproducibility

- `experiments/v3_p5_golden_cases.py`: vendor snapshot of the original FFT, Elastic, Claude inputs in PR #852.
- `experiments/v3_p5_golden_prompt_snapshot.py`: original prompt from PR #852. Only local import path adapted.
- `local_skills/v3_p5_prompts.py`: integrated P5 prompt. Must be **byte-identical** to selected snapshot for the same frozen case input. A changed prompt MUST be versioned/approved, not silently described as the same P5.
- `experiments/v3_p5_baseline_repro.py`: zero-provider default preflight. Optional bounded live replay under explicit `P5_GOLDEN_REPLAY_ONCE` confirmation; a fixed, allowlisted **non-preview** model, exactly 3 cases, maximum 3 requests, 30-second pacing, no SDK automatic retries, no Notion/note/publication.
- Pure baseline creative call in isolated replay: `client.models.generate_content(model=model, contents=prompt)` **without the integrated AIIF Editor Persona, forced temperature, token cap, provider search, or management skeleton.** The separate `local_skills/v3_p5_call_contract.py` checks this configuration. In the integrated `article_revalidation` path, `local_skills/v3_p5_pure_provider.py` now uses the *same no-config authorial prompt* with the existing audited Chat transport, quota and fallback, filtered to nonpreview/nonlite models. Model + transport equivalence with the older proof is not assumed.
- Actual evidence may differ from the old business-management case fixture; retain independent Evidence/Fact/Publication gates in Production.

## Promotion gates: two orthogonal layers

1. **Technical (provider-free, automatable)**: selected prompts equal across three golden cases; original baseline inputs pinned; pure call config without extra persona; no Preview/Lite; stage JSON complete; no persistence path; publication unchanged. CI pass means *technical readiness only*.
2. **Editorial (HUMAN blind evaluation)**: identical per-case source/qualifiers and the archived 83-point reference draft; **different Gemini models across samples/cases are allowed by explicit owner decision on 2026-10-24**. Label the model for every candidate and score article quality directly: opening hook, writer-owned question, evidence-based discovery, thought/feeling movement, naturalness, subject-specific uniqueness, claim accuracy. A mixed-model editorial score can establish whether a manuscript is fun to read, **not** whether an observed delta was caused by a prompt, model or integration change. If a *causal ablation* is desired, only then require same model/config/input for the arms. The 83-point historical aggregate is a reference **not** a valid controlled 83→68 delta. Require fresh human editorial signoff and target score ≥90 before any Production rollout; NO-GO otherwise.

**Explicitly prohibited:** promote based on pytest count, question mark quota, invented emotion, one successful sample, **causal claims from mixed-model arms**, or post-hoc editorial wording adjustments without human scoring. Do not merge PR #861/#862, alter default Classic, relax Fact/Evidence/Publication Gate, or generate/publish notes without owner authorization.

## Known blockage

Live provider returns 503 from multiple Gemini Flash alternatives. Run #40059905022 completed one five-stage `gemini-3.6-flash` sample but not all A/B/C; cannot establish a fair comparative ranking. Continue provider-free work until a bounded live test can finish. **The regular Production Deep Dive provider still injects AIIF Editor Persona.** However the original-only *article_revalidation* Writer now routes through `local_skills/v3_p5_pure_provider.py`, which reuses `_call_model_pool` quota, pacing, health/503 fallback and usage accounting with **empty generation config**, no Preview/Lite, and independent source-native evidence validation. This is isolated opt-in only, not Production adoption. It uses the Production Chat transport instead of the historical Phase0 `models.generate_content` transport, so do not claim byte-for-byte provider identity or an 83-point quality result. The final Editor/Fact/Publication Gates and canonical first management call are unchanged; human quality is **not yet restored or approved**.
