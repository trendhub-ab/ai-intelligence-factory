# Local Skills v4.3.4 Fresh Revalidation — Preregistered Plan

Date: 2026-09-26
Base main: `36d5f902f9d948106c10f23eebbf4317882276a5`

Status: **PREREGISTERED / MEASUREMENT-ONLY / 0 OF 4**

## Purpose

Revalidate the repaired Local Skills stack after Run147 exposed a Gate-input surface
mismatch: the Local Writer article contained the canonicalized bounded action, while
Human Appeal still inspected the stale provider action_text.

PR #562 repairs only that adapter mismatch by synchronizing the compiler-owned parsed
surface into the unchanged Gates.

The prior v4.3.3 series is closed at 2/4 and cannot be resumed.

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
  canonical runtime aligned to Run397 semantics by PR #558
- Gate-input adapter:
  compiler-owned parsed fields synchronized by PR #562
- Fact Gate: unchanged
- Editorial Gate: unchanged
- Publication Readiness Gate: unchanged
- Human Appeal Gate threshold/policy: unchanged

Observed-candidate bookkeeping and audit-only documentation may change between runs
only to prevent candidate reuse. They must not alter article bytes or Gate policy for
an otherwise identical structured input.

## Freshness boundary

This series starts from zero.

Previously measured, failed, retried, repaired, or otherwise observed candidates from
v4.3 / v4.3.1 / v4.3.2 / v4.3.3 are development evidence and **must not count** toward
this series.

This includes Run147:
`Requirement-Bound Verified Commissioning: A Frozen Four-Billion-Parameter Local Model as a Candidate Generator under an External Acceptance Layer with Verification and Release Authority`
(ArXiv `2609.30219v1`).

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

The v4.3.4 series succeeds only if **all 4 of 4 untouched measured candidates** reach:

- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: PASS

A single measured Gate rejection fails this v4.3.4 series.

If a failed measured candidate informs any Writer, Canonicalizer, Evidence Boundary,
Gate-input adapter, Reader precision, action-risk classifier, or Gate repair, that
candidate becomes contaminated development evidence. A repaired result on it cannot
replace the failed blind result, and another fresh validation series is required for
the changed stack.

## Production boundary

Even a 4/4 result does not publish an article or silently switch normal Daily to
Local Skills. It establishes validation evidence for a separate reviewed
Production-integration decision.

No Gate or threshold may be weakened to obtain 4/4.
