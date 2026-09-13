# Run411 — Fact retry specificity for approved apply

## Background

Real approved Apply Run #15 successfully selected the exact RubyGems article, generated with Gemini 3.8, and entered the existing HARD quality retry. After that single retry, Publication Readiness still passed, but valid Fact blockers remained:

- `unsupported vague quantified claim: 数日`
- `LIMITATION_DROPPED`

The Fact Gate is correct. `数日` is supported only when primary Evidence actually contains an equivalent expression such as `several days` / `a few days`. `LIMITATION_DROPPED` means the source contains an explicit limitation/challenge but the manuscript no longer retains one.

## Change

Run411 does not alter validation. It strengthens only the existing approved-lane HARD retry instruction:

1. Every unsupported vague quantified token named by the Gate must be removed or locally replaced with a non-quantified evidence-bounded statement unless the Evidence itself supports that quantity.
2. `LIMITATION_DROPPED` must restore exactly one short limitation that actually exists in primary Evidence; generic caution or an invented limitation is forbidden.
3. When both occur, the same already-budgeted HARD retry must fix both.
4. Existing Evidence, Decision, Score, supported numbers, named entities and constraints remain immutable except where the failing sentence itself must be corrected.

## Safety

- No Gate threshold changes.
- No extra Gemini request.
- No request-budget increase.
- No automatic public publication.
- Installed only inside the exact owner-approved Run399 lane via the existing Run409 overlay boundary.
- Normal Daily, ordinary article validation, Pending Retry and X logic are unchanged.

The next accepted result may proceed through the existing Note Ready sync and then to a private note draft only. Public release remains manual.
