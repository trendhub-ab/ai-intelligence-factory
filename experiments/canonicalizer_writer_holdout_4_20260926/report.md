# Stage 5 — Frozen Canonicalizer + Local Writer Blind Holdout Result

## Primary result

**3 / 4 all-Gate pass (75%).**

This is the first valid Stage 5 quality measurement. The earlier run `36183206952` is excluded because malformed snapshot URLs caused Local Writer input validation to stop before Gate measurement.

- Valid blind run: `36183623639`
- Publication Canonicalizer v3 blob: `6030016136e905d3c611fe93425a7f11133c3028`
- Local Writer v3 blob: `dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2`
- Stage 1-4 records reused for tuning: **0**
- Provider / LLM API calls: **0**
- Production / Gate changes: **none**

## Per-record result

| Source | Record | Fact | Publication | Human | All Gates |
|---|---|---|---|---|---|
| ArXiv | Intern-S2-Preview: Scientific Agentic Foundation Model | PASS | PASS | ACCEPTABLE | PASS |
| HackerNews | Qwen 3.8 27B | PASS | PASS | ACCEPTABLE | PASS |
| HackerNews | Auto-research with codex: How I achieved a 232x Faster Kernel | FAIL: performance_multiplier_scope_lost: a source expectation/benchmark multiplier is presented without preserving attribution/modality and workload-or-condition variability | PASS | ACCEPTABLE | FAIL |
| ArXiv | Exponential quantum advantage for learning signals with a single qubit | PASS | PASS | ACCEPTABLE | PASS |

## What generalized

Three untouched records passed the complete unchanged stack:

- Intern-S2-Preview: Scientific Agentic Foundation Model
- Qwen 3.8 27B
- Exponential quantum advantage for learning signals with a single qubit

For all three, Editorial passed, Publication Readiness passed, and Human Appeal was ACCEPTABLE.

## Single failure

`Auto-research with codex: How I achieved a 232x Faster Kernel` passed Editorial, Publication, and Human Appeal, but Fact Gate rejected one technical-claim issue:

`performance_multiplier_scope_lost`

The problem is not generic prose quality. A performance multiplier from the source was rendered without preserving enough attribution/modality and workload-or-condition scope.

## Interpretation

Stage 5 provides genuine out-of-development-set evidence that the deterministic Canonicalizer + Local Writer architecture generalizes beyond the Stage 4 development set: 3 of 4 untouched records passed the complete stack without any LLM call.

However, the preregistered success criterion was 4/4, so Stage 5 does **not** establish Production readiness.

The uncovered gap is narrower than Stage 3: performance multiplier / benchmark claims need a deterministic scope-preservation contract before prose generation.

## Methodological constraint

This Stage 5 holdout is now contaminated for tuning. If the failed multiplier case is used to design a Canonicalizer v4 rule, Stage 5 cannot be reused to claim validation. A new untouched validation set is required for the next generalization claim.

At the current Content Intelligence DB state, this holdout already consumed all remaining records that met the same structured-field/evidence eligibility rule. Do not weaken evidence eligibility merely to manufacture another validation set.

Draft / Do not merge.
