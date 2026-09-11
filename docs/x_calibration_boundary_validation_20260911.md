# X saved candidate Global Calibration boundary — 2026-09-11

## Purpose

Prove that the already-screened Defense Factory candidate can enter the real Production Global Calibration prompt boundary without repeating Screening, without consuming Gemini quota, and without permitting Stock persistence, Deep Dive generation, or publication.

## Inputs

- saved candidate fixture: `x_discovery/fixtures/defense_factory_boundary_20260911.json`
- saved screening observation: `x_discovery/fixtures/defense_factory_screening_result_20260911.json`
- X provenance post ID: `2097786616311840853`
- canonical primary URL: `https://openai.com/the-defense-factory`
- Raw Decision Score: 88
- Raw Commercial Score: 90
- saved Shelf-life observation used by fixture: 80
- Raw Topic: SECURITY

The candidate and screening fixtures must agree on canonical URL and X post ID. A mismatch fails closed before the Calibration prompt is built.

## Production boundary

The validation uses the installed `pipeline._calibration_prompt`, which is the canonical `screening_protocol.calibration_prompt` surface used by Production `calibrate_candidates()`.

Current policy:

- Global Calibration enabled
- Calibration minimum Raw Score: 55
- Defense Factory Raw Score: 88

Therefore the candidate is eligible for Calibration.

The bounded lane returns `CALIBRATION_BOUNDARY_READY` after constructing exactly one candidate prompt. It does not call a provider.

## Operation ceiling

The contract records `operation_model_request_ceiling = 1` for any later explicitly authorized live Calibration proof. This is an operation-wide ceiling, not merely a per-process retry limit.

No live execute path is enabled by this boundary proof.

## Safety result

- Screening repeated: no
- Gemini/model calls: 0
- Calibration executed: false
- Notion calls: 0
- Stock persistence: false
- Deep Dive selected/generated: false
- X official API calls: 0
- Apify: 0
- FetchLayer: 0
- source/page fetch: 0
- Factory content writes: 0
- publication: false

## CI

`X Bounded Validation CI` compiles and executes the saved-X screening-boundary and Calibration-boundary contracts with `GEMINI_API_KEY`, `NOTION_API_KEY`, and `GH_PAT` blank. The Calibration contract reached the real prompt boundary while all provider/write counters remained zero.

## Next gate

Do not repeat Screening. A future live Calibration proof should be separately authorized and must execute exactly one Calibration request for this saved candidate, with no retry/fallback and with Stock persistence, Deep Dive generation, and publication disabled. The returned calibrated Final Score can then be fed into the already-proven provider-free post-calibration threshold/persistence audit.
