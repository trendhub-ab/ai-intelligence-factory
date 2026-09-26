# Local Skills Daily Canary — Stage 8

Date: 2026-09-26  
Status: **VALIDATION-ONLY / DO NOT MERGE BEFORE LIVE CANARY REVIEW**

## Why this lane exists

The frozen Local Skills stack cannot obtain a new holdout from the existing
Content Intelligence DB because every currently eligible record has already
been consumed by Stages 1–6.

This lane uses normal Daily acquisition to create the fresh holdout instead of
weakening Evidence eligibility or recycling an observed record.

## Measurement path

1. Current Production source acquisition (GitHub / Hacker News / arXiv /
   OfficialVendor).
2. Current legal filter and current Notion URL dedupe.
3. Current Gemini Screening and Calibration.
4. Select one fresh candidate using the current Production portfolio ordering.
5. Run one normal Deep Dive response to obtain the current structured Decision
   fields.
6. Discard the provider-generated article body.
7. Compile the reader-facing article with the frozen Publication Canonicalizer
   v4 + Local Writer v3.
8. Run the unchanged Fact, Editorial, Publication and Human Appeal gates.
9. Save only the private canary audit artifact.

## Safety boundary

- `persist_results=False` is mandatory.
- Canary code raises if persistence is requested.
- No Stock, manuscript, Ready state or note draft is written by the canary.
- No downstream note/publication workflow is dispatched.
- Gemini quality rewrite is disabled for the measured article.
- Deterministic publication rescue is disabled for the measured article.
- Local Skills adds zero provider requests.
- Existing Gate rules and thresholds are unchanged.
- Normal Daily modes remain pinned to `main`; only the explicit canary mode may
  checkout the selected canary branch.

## Primary result

The valid result is exactly one of:

- `accepted`: the frozen Local Skills article reached the existing Gate stack
  and passed under the current disposition.
- `rejected`: the frozen Local Skills article reached the Gate stack and was
  rejected; the audit must retain the individual Gate diagnostics.

No fresh candidate, missing structured fields, no Gate measurement, or any
persistence attempt is an execution failure rather than a quality result.

Audit path: `article_audit/local_skills_daily_canary.json`.
