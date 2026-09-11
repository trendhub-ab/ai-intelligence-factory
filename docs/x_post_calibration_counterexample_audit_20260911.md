# X saved candidate post-calibration counterexample audit — 2026-09-11

## Purpose

Verify the deterministic Factory guards that apply **after** Global Calibration has produced a Final Score, without calling Gemini, Notion, X, Apify, FetchLayer, or any source page.

This is a simulation/audit only. It does not claim that Defense Factory has completed Global Calibration, and it does not persist a Stock row.

## Production invariants under test

- `NOTION_SAVE_THRESHOLD_SCORE = 60`
- `TOP_N_FOR_DEEP_DIVE = 3`
- canonical deterministic helper: `deep_dive_portfolio.select_stocked_deep_dive_candidates`
- Deep Dive eligibility requires both:
  1. Final Score >= Stock threshold
  2. successful Stock persistence represented by a non-empty `notion_page_id`

## Counterexamples

1. Final 59, unpersisted
   - below Stock threshold
   - must not enter Deep Dive selector

2. Final 60, unpersisted
   - meets Stock threshold numerically
   - must still not enter Deep Dive selector because persistence is absent

3. Final 60, synthetic persisted marker
   - must enter the deterministic Deep Dive selector
   - marker is test-only and is never written to Notion

4. Defense Factory hypothetical Final 88, unpersisted
   - must not enter Deep Dive selector

5. Defense Factory hypothetical Final 88, synthetic persisted marker
   - must enter the deterministic selector under the current threshold

## Safety

- Gemini/model calls: 0
- Notion calls: 0
- Factory writes: 0
- X official API calls: 0
- Apify: 0
- FetchLayer: 0
- source/page fetch: 0
- Calibration execution: 0
- article generation: 0
- publication: 0

## Interpretation

The important result is that a high score alone cannot bypass persistence. Even a hypothetical Final 88 remains blocked from Deep Dive until Stock persistence succeeds. Conversely, the threshold boundary behaves correctly: 59 is rejected, while 60 becomes selectable only after persistence.

This closes the provider-free post-calibration routing proof. The next provider-using gate, if authorized, is one bounded Global Calibration request for the already-screened Defense Factory candidate. Screening must not be repeated.
