# Local Skills v4.3.2 fresh broader revalidation plan

Status: PREREGISTERED / MEASUREMENT-ONLY

## Why this is a new series

The previous v4.3.1 fresh series is closed.

Its first valid measured holdout passed all unchanged Gates:

- `PoEM: Predicting RL Outcomes from Existing Policies`
- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: PASS

A later run accidentally reused PoEM before the observed-candidate ledger was updated. That duplicate run was ineligible as a fresh holdout and is not counted.

The next valid fresh holdout was:

- `OpenAI says agents leaked 53 images from ChatGPT users`
- Fact: FAIL
  - `HIGH_RISK_ACTION_UNSUPPORTED: downgrade to LOW required`
  - `unsupported vague quantified claim: 数ヶ月`
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: BLOCK

Run 36232493018 therefore failed v4.3.1.

PR #555 repaired only the demonstrated pre-Gate boundary defects:
- an explicitly rejected action such as `本番移行は見送り` no longer escalates to HIGH risk merely because the phrase `本番移行` appears;
- Local Evidence Boundary stage8-v4 fails closed on unsupported vague temporal quantities and uses a deterministic field fallback instead of emitting malformed prose.

No Gate threshold was weakened. Because the measured stack changed after observing a fresh Gate failure, a new series is required.

## Frozen validation stack

- Local Writer blob: `f3076ab88316cf9ada97067aa9af21480dff6459`
- Publication Canonicalizer blob: `414089a14c238f104b2866507ddf8521c2baf420`
- Evidence Boundary: `stage8-v4`
- Evidence Boundary blob: `7bd7256dc52b675c71e78065fd616398c52ef0ea`
- Source-Boundary blob: `69fa0edcf18b5c9a99e9a32f9dd17809c8d9cbb9`
- Pipeline / Action-risk implementation blob: `be94b28a298a2d09945a12aae7c0d439ac64cede`
- Canary candidate-exclusion blob: `b01b36af7e9b0714837068456868e9fcdafc1f30`
- Fact Gate thresholds: unchanged
- Editorial Gate: unchanged
- Publication Readiness Gate: unchanged
- Human Appeal Gate: unchanged

No Writer wording repair, Gate-threshold weakening, provider article reuse, quality rewrite, or deterministic publication rescue is permitted during this series.

## Holdout eligibility

Each counted candidate must be untouched before selection and chosen only through the current Production acquisition / dedupe / legal / Screening / Calibration / Evidence preconditions.

Previously observed Local Skills candidates are excluded, including all candidates that informed validation, repair, or canary orchestration. In particular:

- `PoEM: Predicting RL Outcomes from Existing Policies`
- `Minimally Invasive Steering of Language Models`
- `OpenAI says agents leaked 53 images from ChatGPT users`
- `RAPID: Robot Agentic Programming from Demonstrations`
- `Revelations of dozens more platforms hit by OpenAI agents`
- `Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure`

A candidate rejected before any Deep Dive provider send because of Evidence/Source preconditions is an eligibility/backfill event and does not count.

A Deep Dive/provider execution failure before compiler/Gate measurement does not count, but the candidate is thereafter observed and must not later be claimed as untouched.

## Execution contract

Use only the explicit `local_skills_canary_validation` ONE-SHOT lane.

For each run:

- `persist_results=false`
- at most one measured Deep Dive candidate
- provider-generated article body is discarded
- Local Skills article body provider calls = 0
- Editorial Eyecatch provider calls = 0
- no quality rewrite
- no deterministic publication rescue
- no Notion article/Ready persistence
- no note publication
- no downstream publication fan-out
- unchanged current Gates determine final disposition

Do not overlap measured runs.

## Success criterion

The v4.3.2 stack must obtain four untouched measured holdouts, and all four must satisfy:

- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: PASS

Any eligible measured Gate rejection fails this series.

If a failed measured candidate informs another implementation repair, that candidate becomes contaminated and a new validation series is required after the stack changes.

Four passes do not automatically enable Production publication. A separate reviewed Production integration decision is required.

## Provider safety

- respect repository-local persistent model counters;
- do not bypass a model safety cap;
- at most one measured Deep Dive candidate per run;
- stop the sequence on repeated provider 503s or other instability;
- do not spend provider quota on Local Skills article generation or Eyecatch.

This preregistration itself performs no external model call.
