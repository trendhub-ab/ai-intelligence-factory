# Local Skills Stage 8 Repair — Evidence Boundary + Reader Accessibility

Date: 2026-09-26

Status: **DEVELOPMENT REPAIR — NOT A FRESH VALIDATION RESULT**

## Triggering fresh Production measurement

The measurement-only Daily canary produced a fresh rejection for:

- Subject: `Jevmem – automatic project memory for Claude Code, built on Jev`
- Source: Hacker News
- Fact Gate: FAIL — `unsupported numeric claim: 約0.02円`
- Editorial Gate: PASS
- Publication Gate: PASS
- Human Appeal: WEAK
  - non-engineer access failure
  - multi-axis reader weakness
- Final disposition: BLOCK
- Persistence / Ready / note publish: none

The immediately preceding fresh canary article had passed all Gates. Therefore the
fresh evidence available before this repair is one PASS and one FAIL. The Jevmem
record is contaminated after this repair and may never be counted again as fresh
validation.

## Repair

No Gate rule or threshold is changed.

1. **Verified-evidence numeric boundary**
   - Production passes its actual primary-source verification context into the
     Local Skills compiler.
   - Reader-facing sensitive numeric expressions survive only when the same
     numeric value is present in that verification context.
   - Derived conversions such as a yen amount absent from primary evidence are
     removed before Local Writer rendering.
   - Decision, Score, source identity and URLs are untouched.

2. **Local Writer v4 reader foothold**
   - Adds one first-use subject bridge to every layout.
   - The bridge uses only the stored `source_summary`; it does not call a model or
     add external facts.
   - Layout-varied conversational wording gives non-engineers an early answer to
     “what is this?” without weakening technical detail.

3. **Fresh-holdout hygiene**
   - All canary-observed records, including the prior all-Gate PASS and Jevmem
     FAIL, are excluded from future fresh-validation claims.

## Fixed implementation

- Publication Canonicalizer v4 remains unchanged:
  `414089a14c238f104b2866507ddf8521c2baf420`
- Local Writer v4:
  `0fafb7c878d26cd4eb4f4293c76e6d5bcbdb6ec8`
- Evidence Boundary:
  `stage8-v1`
- Local Skills adds zero article-generation provider calls.
- Normal Production mode remains unchanged; the repaired stack is still
  reachable only from `local_skills_canary_validation`.

## Validation rule

Passing the contaminated Jevmem regression after this change is only a repair
check. Production readiness requires a new untouched Daily candidate through the
same measurement-only canary and unchanged Gates.
