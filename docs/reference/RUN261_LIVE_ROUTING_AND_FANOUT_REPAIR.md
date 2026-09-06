# Run261 — Live Routing and Fan-out Repair

Date: 2026-09-06

## Why this run exists

Production ONE-SHOT #28 was the first live article run after Run260. It proved two gaps that zero-API unit tests had not falsified:

1. `quality_retry` could enter the live Deep Dive path with Gemini 3.7 first even though Run260 intended Gemini 3.8 first.
2. ChatOps could dispatch ONE-SHOT with `GH_PAT`, but successful ONE-SHOT completion still did not produce the expected direct `workflow_run` fan-out.

Run261 repairs both without weakening any content gate, raising any Gemini request ceiling, resuming scheduled Daily, or enabling public note publication.

## Evidence and falsification

### Quality routing

Observed in ONE-SHOT #28 usage telemetry:

- fresh Deep Dive used Gemini 3.7 as intended;
- one `quality_retry` selected Gemini 3.7 first, returned two 503 responses, then fell through to Gemini 3.8;
- therefore the problem was not a misleading log or a 3.8-first fallback sequence: the first quality model was genuinely wrong.

Ruled out:

- the 503 recovery layer changing initial model order — it only controls run-local unavailable state;
- Fact/Evidence/Publication gates changing model order;
- an exhausted Gemini 3.8 Factory budget — the run had 3.8 capacity remaining.

Root cause class: the original Run260 test asserted `_call_model_pool` directly, while production enters model generation through `_call_deep_dive_pool`. The production entrypoint itself was not protected by the quality-first contract.

### Workflow fan-out

Observed in ONE-SHOT #28:

- upstream workflow name exactly matched `Daily Intelligence & Content Pipeline [ONE-SHOT]`;
- upstream branch was `main`;
- upstream conclusion was `success`;
- direct downstream workflow files existed on the default branch and subscribed to that exact workflow name;
- nevertheless no new direct `workflow_run` execution appeared after completion.

Therefore the fix does not keep relying on passive `workflow_run` behavior for the direct ONE-SHOT fan-out.

## Runtime repair

`run260_gemini_model_routing.py` now protects both surfaces:

- `_call_model_pool` remains defense in depth;
- `_call_deep_dive_pool` is now the authoritative live-path guard for quality repair.

Routing remains:

- fresh Deep Dive: `3.7 -> 3.8 -> 3.6 -> 3.5`;
- model-based quality repair: `3.8 -> 3.6 -> 3.5 -> 3.7`.

The live-path wrapper delegates exactly once to the existing `_call_model_pool`. Existing retry/fallback/cooldown and per-run request accounting remain authoritative. No additional provider loop exists.

## Workflow repair

After a successful ONE-SHOT, `.github/workflows/daily-one-shot.yml` explicitly dispatches, using `GH_PAT`:

1. `note-ready-sync.yml`
2. `subscriber-decision-brief.yml`
3. `cross-db-contract-guard.yml`

Missing `GH_PAT` is fail-closed. Dispatch failures fail the fan-out step.

To prevent double writes if GitHub passive behavior changes later, those three direct downstream workflows no longer subscribe passively to ONE-SHOT completion. Their independent triggers remain intact:

- Note Ready retains `workflow_dispatch` and relevant `push` reconciliation;
- Subscriber Decision Brief retains Inventory Bootstrap `workflow_run`, `workflow_dispatch`, push and PR validation;
- Cross DB retains Member Presentation `workflow_run`, `workflow_dispatch`, push and PR validation.

## Workflow configuration reconciliation

The production and Pending Retry ONE-SHOT environments now explicitly expose:

- `GEMINI_38_FLASH_DAILY_BUDGET=18`;
- article pool `gemini-3.7-flash,gemini-3.8-flash,gemini-3.6-flash,gemini-3.5-flash`.

This does not increase the existing Flash safety ceiling. The authoritative Deep Dive per-run request budget remains `12`.

The separate Product Review model routing is intentionally unchanged.

## Regression contract

Run261 must prove at minimum:

- live `_call_deep_dive_pool(..., kind="quality_retry")` reaches the existing model pool exactly once with 3.8 first;
- live fresh Deep Dive still has 3.7 first;
- direct ONE-SHOT downstream targets all accept `workflow_dispatch`;
- no direct downstream workflow passively subscribes to ONE-SHOT;
- Daily remains hard-PAUSED;
- no public note release is introduced;
- Deep Dive request budget remains 12 and Gemini 3.8 repository-local safety budget remains at most 18.

## Live-proof boundary

Run261 code/CI can prove routing and dispatch contracts without spending Gemini quota. It cannot truthfully prove the next real provider selection or GitHub dispatch execution until the next intentional ONE-SHOT runs on the merged main branch.
