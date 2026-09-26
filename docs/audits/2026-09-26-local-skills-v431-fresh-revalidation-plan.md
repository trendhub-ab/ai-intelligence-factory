# Local Skills v4.3.1 fresh broader revalidation plan

Status: PREREGISTERED / MEASUREMENT-ONLY

## Why this is a new series

The previous v4.3 broader-validation series ended after its third measured holdout because:

- measured candidate: `RAPID: Robot Agentic Programming from Demonstrations`
- Fact Gate: FAIL
- Editorial Gate: PASS
- Publication Readiness Gate: PASS
- Human Appeal Gate: ACCEPTABLE
- final disposition: BLOCK

The failure was reproduced as a Source-Boundary false positive on the generic template word `Evidence` in:

`今は導入を急がず、追加Evidenceと今後の動きを追うのが妥当です。`

PR #552 changed only the narrow Source-Boundary named-entity ignore set so the generic article-template word `Evidence` is not treated as a product/entity name. Existing unknown-product blocking remains covered by regression.

Because a Gate implementation changed after observing a measured holdout, the previous series must not continue counting. This document preregisters a new fresh series.

## Frozen validation stack

- Local Writer v4.3 blob: `f3076ab88316cf9ada97067aa9af21480dff6459`
- Publication Canonicalizer v4 blob: `414089a14c238f104b2866507ddf8521c2baf420`
- Source-Boundary implementation blob: `69fa0edcf18b5c9a99e9a32f9dd17809c8d9cbb9`
- Evidence Boundary: `stage8-v3`
- Fact Gate thresholds: unchanged
- Editorial Gate: unchanged
- Publication Readiness Gate: unchanged
- Human Appeal Gate: unchanged

No Writer wording repair, no Gate-threshold weakening, and no Publication rescue change is permitted during the series.

## Holdout eligibility

Each measured candidate must be untouched by Local Skills development before selection and must be selected only through the current Production acquisition / dedupe / legal / Screening / Calibration / Evidence preconditions.

Previously observed Local Skills candidates are excluded, including:

- Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure
- Revelations of dozens more platforms hit by OpenAI agents
- RAPID: Robot Agentic Programming from Demonstrations

A candidate rejected before Deep Dive because of Evidence/Source preconditions is an eligibility/backfill event and does not count as a measured holdout.

An execution failure before Gate measurement does not count.

## Execution contract

Use only the explicit `local_skills_canary_validation` ONE-SHOT lane.

For each run:

- `persist_results=false`
- at most one measured Deep Dive candidate
- provider-generated article body is discarded
- Local Skills article body provider calls = 0
- Editorial Eyecatch provider calls = 0
- no quality rewrite
- no deterministic publication rescue for the measured article
- no Notion article/Ready persistence
- no note publication
- no downstream publication fan-out
- unchanged current Gates determine final disposition

Do not overlap measured runs.

## Success criterion

The new stack must obtain four untouched measured holdouts, and all four must satisfy:

- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: PASS

Any measured Gate rejection fails this series.

If a failed measured candidate informs another implementation repair, that candidate becomes contaminated and a new validation series is required after the stack changes.

Four passes do not automatically enable Production publication. A separate reviewed Production integration decision is required.

## Provider/quota safety

At preregistration time, the current `gemini-3.5-flash` persistent counter has reached 18/18 for the active provider quota date. Therefore:

- do not start this new series until an eligible Deep Dive model has confirmed available quota;
- do not bypass the persistent counter;
- do not weaken the one-measured-candidate-per-run limit;
- stop on repeated 503s or provider instability.

This plan itself performs no external model call.
