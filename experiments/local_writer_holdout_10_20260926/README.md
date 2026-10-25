# Local Writer Stage 3 — Blind Holdout 10

This experiment freezes Local Writer v3 before measuring the holdout set.

- Frozen writer commit: `4b139edfd3fdb845723b850e80039b1c28f05e59`
- Frozen writer blob: `dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2`
- Holdout size: 10
- Prior experiment records excluded: 6
- Existing article body used for selection: **false**
- Product Hunt: excluded as retired production source
- X: eligible, but 0 records met the structured-field/evidence filter
- Notion writes: none
- Provider/API calls: none
- Production/Gate changes: none

## Pre-registered selection

Eligible records must have all Local Writer structured fields and evidence state `Source Native`, `URL Context`, or `URL + Search`.

Selection is deterministic and result-blind:

1. Hash `local-writer-holdout-v1|<Notion page URL>` with FNV-1a.
2. Take the two lowest hashes from each of GitHub, HackerNews, ArXiv, and OfficialVendor.
3. Fill the remaining two slots from all remaining eligible records by the same hash.
4. Do not inspect or use the existing article body.
5. Do not modify Local Writer v3 after holdout measurement starts.

## Success metric

Measure the unchanged Production Fact / Editorial / Publication / Human Appeal stack.
The primary metric is exact all-Gate pass rate out of 10. Failures are findings, not authorization to tune v3 on this holdout.

Do not merge. Validation only.
