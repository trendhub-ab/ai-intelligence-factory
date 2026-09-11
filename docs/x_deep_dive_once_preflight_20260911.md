# X Saved Stock -> Deep Dive One-Turn Preflight — 2026-09-11

## Purpose

Prepare the already-persisted Defense Factory Stock for one bounded, non-persistent Deep Dive generation attempt without repeating Screening, Calibration, or Stock persistence.

## Pinned input

- canonical URL: `https://openai.com/the-defense-factory`
- persisted Notion page: `3d8479ff-dca9-81d2-aff1-f203bf02222f`
- Final Decision Score: `88`
- saved Stock observation SHA-256 is enforced by `x_discovery.stock_deep_dive_handoff.EXPECTED_STOCK_SHA256`

## Canonical entrypoint

`production_pipeline.py` mode `x_saved_stock_deep_dive_once` delegates only to `x_discovery.deep_dive_once.run_from_paths`.

The lane rebuilds the persisted item and passes the real Production Stock/Deep Dive selector before any model request.

## Operation-wide request contract

The live proof is not armed by CI. Explicit execution requires all of:

- `AIIF_X_DEEP_DIVE_EXECUTE=true`
- fixed operation `defense-factory-deep-dive-20260911`
- first workflow attempt only
- durable GitHub `runtime-state` quota counter
- create-only non-expiring operation claim at `.runtime/operations/defense-factory-deep-dive-20260911.json`
- process Gemini daily budget exactly `1`, unused
- Deep Dive model budget exactly `1`, unused
- model pinned to `gemini-3.6-flash`

The operation claim is not released on timeout, 429, 503, malformed output, or any ambiguous result. Therefore a failed/ambiguous live attempt cannot be silently reissued under the same authorization.

## Hidden-call controls

Only for this bounded process, the lane forces:

- Quality Retry = `0`
- URL Context = disabled
- Google Search grounding = disabled
- model fallback pool = one pinned model
- SDK HTTP retry attempts = `1`
- automatic function calling = disabled

These process-local overrides are restored afterwards.

## Pre-model evidence gate

Primary-source preparation, freshness resolution, and evidence-sufficiency checks occur before the irreversible operation claim/model request. If evidence remains insufficient, the lane stops without spending the model authorization.

After preflight, the verified source context is frozen into the generation call so the normal article generator does not repeat source acquisition.

## Persistence/publication boundary

Generation calls the existing Production `generate_intelligence_report(..., persist_results=False)` path.

For this proof:

- Notion article/content writes: forbidden
- Stock writes: forbidden
- eyecatch generation/upload: disabled
- Telegram side effects: disabled
- note draft/publication: impossible from this lane
- Screening: not re-run
- Global Calibration: not re-run
- Stock persistence: not re-run

The output record stores status, quality status, article character count/hash and Gemini usage metadata; it does not persist the generated article into Factory/Notion.

## Offline proof

`tests/test_x_deep_dive_once.py` verifies authorization, page pinning, one non-persistent generation, retry/tool suppression, and restoration of process globals.

`tests/test_x_deep_dive_runtime.py` installs the canonical Production runtime layers and uses a mocked HTTP 503 transport. It verifies the strict provider path makes exactly one SDK HTTP attempt, consumes exactly one process request and one Deep Dive model-budget unit, and reserves the persistent quota counter exactly once.

These tests are included in `X Bounded Validation CI` with Gemini/Notion/GH credentials blank.

## Live execution gate

No temporary live-trigger workflow is retained in the branch at this preflight stage. A live attempt should be armed only as a single-purpose execution path, observed to completion, then removed immediately. Publication remains a separate later decision even if the generated article passes quality gates.
