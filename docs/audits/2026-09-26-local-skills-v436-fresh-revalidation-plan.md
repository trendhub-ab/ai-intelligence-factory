# Local Skills v4.3.6 Fresh Revalidation — Preregistered Plan

Date: 2026-09-26
Base main: `bfc02da7fc0dd4a1d9766e26d9ac061cbfb3e9eb`

Status: **COMPLETE / MEASUREMENT-ONLY / 4 OF 4 PASS**

## Purpose

Revalidate the Local Skills stack after Run153 exposed a genuine non-engineer
accessibility failure and malformed prose left by evidence-bounded numeric deletion.

Run153 measured:
- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: WEAK
- issue: `reader_value_review:non_engineer_access_failure`

PR #570 repairs only the publication quality defects demonstrated by that run:
- first-use plain-language bridges for common robotics concepts already present in
  structured evidence;
- deterministic cleanup of grammar residue left after unsupported numeric spans are
  removed;
- Run153 candidate marked observed/contaminated.

No Gate threshold or Human Appeal policy was weakened.

The prior v4.3.5 series is closed after its first measured rejection and cannot be
resumed.

Success requires **4/4 untouched measured candidates** to pass every existing Gate.

## Frozen quality stack

- Local Writer blob:
  `204cce30ab838e0d6dac9cbe762d0a82ff02f1aa`
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
- Fact false-negative evidence precision:
  hardware uncertainty scoping repaired by PR #567
- Non-engineer robotics accessibility and numeric-deletion prose cleanup:
  repaired by PR #570
- Fact / Evidence strictness: unchanged
- Editorial Gate: unchanged
- Publication Readiness Gate: unchanged
- Human Appeal Gate threshold/policy: unchanged

Observed-candidate bookkeeping and audit-only documentation may change between runs
only to prevent candidate reuse. They must not alter article bytes or Gate policy for
an otherwise identical structured input.

## Freshness boundary

This series starts from zero.

Previously measured, failed, retried, repaired, or otherwise observed candidates from
v4.3 through v4.3.5 are development evidence and **must not count** toward this series.

This includes Run153:
`Rolling-WAM: World Action Models with Rolling Imagination`
(ArXiv `2609.30247v1`).

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

The v4.3.6 series succeeds only if **all 4 of 4 untouched measured candidates** reach:

- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: PASS

A single measured Gate rejection fails this v4.3.6 series.

If a failed measured candidate informs any Writer, Canonicalizer, Evidence Boundary,
Gate-input adapter, Fact precision, Reader precision, accessibility bridge, or Gate
repair, that candidate becomes contaminated development evidence. A repaired result
on it cannot replace the failed blind result, and another fresh validation series is
required for the changed stack.

## Production boundary

Even a 4/4 result does not publish an article or silently switch normal Daily to
Local Skills. It establishes validation evidence for a separate reviewed
Production-integration decision.

No Gate or threshold may be weakened to obtain 4/4.


## Completion record

Fresh measurements completed on 2026-09-26:

- Run154: PASS
- Run155: PASS
- Run156: PASS
- Run159: PASS

Run157 and Run158 do not count toward the four measurements because provider failure occurred before compiler/Gate measurement, as allowed by the preregistered execution boundary.

Run159 measured:
- candidate: `DeepSeek Elastic Compute:A Sandbox Infrastructure for Effective Agentic Training`
- canonical source: ArXiv `2609.22978`
- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- final disposition: PASS
- `persist_results=false`
- Local Skills article-generation provider calls: 0
- Editorial Eyecatch provider calls: 0

Operational note: the Deep Dive provider request succeeded on `gemini-3-flash-preview` after Provider Health Routing, while the generated provider article surface remained discarded and was not reused by the Local Skills compiler.

This completes the preregistered v4.3.6 Fresh series at 4/4. Production integration remains a separate reviewed decision.
