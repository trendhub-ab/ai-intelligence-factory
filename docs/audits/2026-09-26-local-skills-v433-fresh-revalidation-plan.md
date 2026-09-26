# Local Skills v4.3.3 Fresh Revalidation — Preregistered Plan

Date: 2026-09-26
Base main: `320eb20ad98878e9c05049b78104d7c3715c3107`

Status: **PREREGISTERED / MEASUREMENT-ONLY / 0 OF 4**

## Purpose

Revalidate the Local Skills stack after the Run 142 Human Appeal failure exposed a
Reader repetition-precision mismatch and PR #558 aligned the canonical runtime with
the already-promoted Run397 semantic repetition contract.

The prior v4.3.2 series is closed and cannot be resumed.

Success requires **4/4 untouched measured candidates** to pass every existing Gate.

## Frozen quality stack

The following quality-producing surfaces must remain unchanged for all four measurements:

- Local Writer v4.3 blob:
  `f3076ab88316cf9ada97067aa9af21480dff6459`
- Publication Canonicalizer v4 blob:
  `414089a14c238f104b2866507ddf8521c2baf420`
- Evidence Boundary:
  `stage8-v4`
- Action risk classification:
  negation-aware repair from PR #555
- Reader repetition precision:
  canonical runtime aligned to Run397 semantic predicate-bearing repetition by PR #558
- Fact Gate: unchanged
- Editorial Gate: unchanged
- Publication Readiness Gate: unchanged
- Human Appeal Gate threshold/policy: unchanged

Observed-candidate bookkeeping and audit-only documentation may change between runs
only to prevent candidate reuse. They must not alter article bytes for an otherwise
identical structured input.

## Freshness boundary

This series starts from zero.

Previously measured, failed, retried, repaired, or otherwise observed candidates from
v4.3 / v4.3.1 / v4.3.2 are development evidence and **must not count** toward this
series. This includes the Run 142 candidate:
`Coding Agents for Generalized Task and Motion Planning Problems`
(ArXiv `2609.30233v1`).

No candidate may be selected because its article outcome is already known.

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
quality result. An execution/provider failure before Gate measurement does not count
toward the four quality measurements.

## Success criterion

The v4.3.3 series succeeds only if **all 4 of 4 untouched measured candidates** reach:

- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: PASS

A single measured Gate rejection fails this v4.3.3 series.

If a failed measured candidate informs any Writer, Canonicalizer, Evidence Boundary,
Reader precision, action-risk classifier, or Gate repair, that candidate becomes
contaminated development evidence. A repaired result on it cannot replace the failed
blind result, and another fresh validation series is required for the changed stack.

## Production boundary

Even a 4/4 result does not publish an article or silently switch normal Daily to
Local Skills. It establishes validation evidence for a separate reviewed
Production-integration decision.

No Gate or threshold may be weakened to obtain 4/4.
