# Local Skills v4.3 Broader Validation — Preregistered Plan

Date: 2026-09-26
Base main: `f9f0813d38c576f3d95b87db52d61560e62273f5`

Status: **PREREGISTERED / MEASUREMENT-ONLY**

## Purpose

Determine whether the exact Local Skills v4.3 publication stack generalizes across
multiple untouched current-Daily candidates before normal Production activation is
considered.

This plan reuses the Stage 5 preregistered success standard: **4/4 all-Gate PASS**.
It does not lower the criterion after seeing the v4.3 first fresh result.

## Frozen quality stack

The following quality-producing surfaces must remain unchanged for all four
measurements:

- Local Writer v4.3 blob:
  `f3076ab88316cf9ada97067aa9af21480dff6459`
- Publication Canonicalizer v4 blob:
  `414089a14c238f104b2866507ddf8521c2baf420`
- Evidence Boundary:
  `stage8-v3`
- Fact Gate: unchanged
- Editorial Gate: unchanged
- Publication Readiness Gate: unchanged
- Human Appeal Gate: unchanged

Observed-candidate bookkeeping and audit-only documentation may change between
runs so a measured record cannot be selected again. Such bookkeeping must not
change article bytes for an otherwise identical structured input.

## Four-measurement series

Measurement 1 is already complete and was frozen before this plan:

1. `Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure`
   - ArXiv `2609.30217v1`
   - all-Gate PASS
   - Run `36217425671`

This is **1/4**.

Three additional measurements must use untouched candidates selected by the same
current Production acquisition / dedupe / Screening / Calibration / Evidence
preconditions. No candidate may be selected because of a known article outcome.

## Per-measurement execution boundary

- explicit `local_skills_canary_validation` ONE-SHOT only
- `persist_results=false`
- at most one measured Deep Dive candidate per run
- provider-generated article body discarded
- Local Skills article-generation provider calls: 0
- Editorial Eyecatch provider call: 0
- no quality rewrite
- no deterministic publication rescue for the measured article
- no Notion article / Ready persistence
- no note publication
- no downstream publication fan-out
- unchanged current Gates determine the disposition

Pre-Deep-Dive Evidence/Source rejection is an eligibility/backfill event, not a
quality result. An execution failure before Gate measurement does not count toward
the four quality measurements.

## Success criterion

Broader validation succeeds only if **all 4 of 4 untouched measured candidates**
reach:

- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: PASS

A single measured Gate rejection makes this v4.3 broader-validation series fail.

If a failed measured candidate informs any Writer, Canonicalizer, Evidence
Boundary, or Gate repair, that candidate becomes contaminated development evidence.
A repaired result on it cannot replace the failed blind result, and a new validation
series is required for the changed stack.

## Production boundary

Even a 4/4 result does not itself publish an article or silently switch normal
Daily to Local Skills. It establishes the validation evidence required to consider
a separate, reviewed Production-integration change.

No Gate or threshold may be weakened to obtain 4/4.
