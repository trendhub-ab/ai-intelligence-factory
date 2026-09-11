# X Discovery watchlist policy

This directory separates the live/bootstrap acquisition list from future expansion candidates.

## Active bootstrap list

`ai_core_20.json` is the only watchlist consumed by the current bootstrap workflow. The workflow itself requires exactly 20 unique handles. Do not expand or replace this file while production handoff validation is incomplete.

## Candidate-only registry

`ai_candidate_30.json` is inert inventory only. Every account is explicitly `monitoring_enabled: false`, and the current workflow does not read this file. Adding or editing candidate rows must not trigger X, Apify, FetchLayer, Gemini, or Factory calls.

Candidate inclusion favors accounts that can add information not captured by official organization feeds: implementation details, evaluations, failure modes, comparisons, research interpretation, practical experiments, and links to primary sources. Popularity alone is not sufficient.

## Promotion gate

No candidate may become an acquisition target until all of the following are true:

1. The existing core-20 path is verified end-to-end through the bounded Factory validation lane.
2. A saved X discovery candidate has passed that lane without production persistence or publication.
3. De-duplication failure is fail-closed.
4. The total provider/model request ceiling for the validation run is fixed and disclosed before execution.
5. Incremental non-duplicate useful yield and acquisition cost are measured.
6. The account handle and recent signal quality are manually re-verified immediately before promotion.

Expansion should be staged rather than moving directly from 20 to 50. The first review point is 30 active targets; only proceed toward 50 if incremental value justifies the additional cost. A likely steady-state policy is high-frequency monitoring for the highest-value core set and lower-frequency or rotating monitoring for the remainder.

## Free-tier invariant

Candidate inventory is free to maintain. Acquisition is not. Changes in this directory must never silently increase active profile count, polling frequency, per-profile post count, provider charge ceiling, or model-call budget.
