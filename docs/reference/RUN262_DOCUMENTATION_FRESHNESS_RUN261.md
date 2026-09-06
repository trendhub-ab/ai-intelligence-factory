# Run262 — Canonical Run261 Documentation Freshness

Date: 2026-09-06

## Why this run exists

Run261 was merged only after live evidence, required falsification, full pytest and synthetic regression proved its code/workflow repair. A post-merge direct audit of `main` then found a separate defect: the canonical specification still described the superseded Run260/Run259 mechanisms as current.

The stale canonical text said, in effect, that:

- Article Model Routing authority was still Run260;
- Subscriber Decision Brief and Note Ready directly followed ONE-SHOT through passive `workflow_run`;
- Run259's ChatOps GH_PAT fix was expected to preserve the downstream passive chain;
- quality routing was described only as `_call_model_pool` routing.

Those statements no longer matched merged Production after Run261.

## Falsification

The discrepancy was not treated as harmless prose drift because `AI_Intelligence_Factory_最終仕様書.md` is the second-highest Production authority after current `main` code/tests/workflows. Leaving an obsolete operational mechanism there could cause a future change to reintroduce the exact fan-out defect Run261 removed.

The existing `documentation_freshness_guard.py` was inspected. It correctly protected many broad markers, member destinations, quota ceilings and sync-order requirements, but it did not assert the exact current Run261 mechanisms. As a result, a specification could contain `Run211`, `Run259`, `Run260` and other expected words while still being operationally stale.

## Canonical corrections

The canonical specification now states:

- Article Model Routing Baseline is Run261;
- Fresh Deep Dive remains `3.7 -> 3.8 -> 3.6 -> 3.5`;
- model-based quality repair remains `3.8 -> 3.6 -> 3.5 -> 3.7`;
- Run261 enforces quality ordering at the real Production `_call_deep_dive_pool` entrypoint, while the Run260 `_call_model_pool` wrapper remains defense in depth;
- ONE-SHOT direct downstream fan-out is explicit GH_PAT-authenticated `workflow_dispatch` from `daily-one-shot.yml`;
- direct targets are `note-ready-sync.yml`, `subscriber-decision-brief.yml`, and `cross-db-contract-guard.yml`;
- those direct targets do not also passively subscribe to ONE-SHOT completion;
- Subscriber's independent Inventory Bootstrap `workflow_run` remains and only `[apply]` may write;
- Run259 remains the ChatOps-to-ONE-SHOT credential authority, while Run261 is the direct post-run fan-out authority.

## New fail-closed guard

`run262_documentation_contract_guard.py` is zero-network and zero-provider. It compares the canonical specification with the live Run261 routing and workflow surfaces and fails when any of the following regress:

- Run261 is no longer identified as current Article Model Routing authority;
- the canonical spec revives passive ONE-SHOT fan-out wording;
- the live `_call_deep_dive_pool` quality-routing assignment disappears;
- explicit downstream GH_PAT dispatch disappears;
- any direct fan-out target ceases to accept `workflow_dispatch`;
- a direct target regains a passive ONE-SHOT `workflow_run` subscription;
- the Subscriber Inventory apply-only independent path is lost;
- Run261 or quota reference documents stop carrying the current contract.

The guard and its unit tests execute inside the already-required `falsify-all-tracked-surfaces` status check. No branch-ruleset weakening or new bypass is introduced.

## Non-changes

Run262 changes documentation and documentation regression protection only. It does not change:

- Gemini provider routing behavior introduced by Run261;
- Deep Dive per-run request budget of 12;
- repository-local Gemini 3.8 safety ceiling of 18;
- Pending Retry budgets/cooldown;
- article Fact/Evidence/Decision or publication gates;
- Screening model pool;
- deterministic zero-API rescue;
- Notion schema or member data semantics;
- scheduled Daily hard-PAUSED state;
- human-only public note publication.

Gemini/model requests used for Run262 validation: **0**.

## Live-proof boundary

Run262 can prove that documentation and current code/workflow contracts agree. It does not itself constitute a new live Gemini article-generation run or a live ONE-SHOT downstream fan-out test. Those remain intentionally deferred to the next explicitly requested Production ONE-SHOT.
