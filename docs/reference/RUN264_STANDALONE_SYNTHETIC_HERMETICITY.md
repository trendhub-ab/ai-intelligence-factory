# Run264 — Standalone Synthetic Hermeticity

Date: 2026-09-06

## Incident

After Run263 merged, the required Integration signal was green, including full pytest and its Production-stack synthetic smoke, but the push-triggered `Synthetic Regression Suite` failed on main.

The failing job was `101502362476` from workflow run `34039060035` on main SHA `d3ad67900be24fe594f3262eb6ce616616c8f9e3`.

The standalone workflow executed `python -m unittest discover -s tests -v`. That bypassed the pytest autouse network guard introduced by Run263 and imported `pipeline` with the repository-backed persistent Gemini counter enabled. The concrete failure was Run130's zero-API contract: `pipeline.PERSISTENT_GEMINI_COUNTER.enabled` was `True` when the regression contract requires `False`.

The same run also emitted incidental outbound GitHub attempts using test credentials. They were not Production writes, but they proved the standalone workflow was not hermetic.

## Correction

`.github/workflows/regression.yml` now uses the same deterministic test baseline as Integration CI:

- `ubuntu-24.04`
- Python `3.11.16`
- pinned checkout/setup-python action SHAs
- `GEMINI_PERSISTENT_DAILY_COUNTER=false`
- production requirements installed through `requirements-ci-constraints.txt`
- pytest `8.4.2`
- `python -m pip check`
- compile current Python surfaces
- `integration_stability_guard.py`
- `python -m pytest -q tests` so the autouse external-network guard is active
- existing regression harness self-test and requested smoke/core/full suite remain intact

No Production article logic, quality gate, Gemini routing, Notion write path, or public note publication behavior changes in Run264.

## Recurrence prevention

`integration_stability_guard.py` now validates the standalone workflow as part of the deterministic CI contract. It fails closed if the workflow:

- reintroduces unittest discovery for the full suite,
- enables the persistent remote Gemini counter,
- drops the locked dependency graph,
- unpins the Python/action runtime,
- stops using pytest/network isolation, or
- removes the synthetic harness execution.

`Integration Reconciliation CI` now includes `.github/workflows/regression.yml` in its pull-request path filter, so future standalone-regression workflow changes trigger the required Integration check before merge.

## Acceptance criteria

Run264 is complete only when:

1. repository falsification is green on the PR,
2. Integration full deterministic pytest is green on the PR,
3. Integration Production-stack synthetic smoke is green,
4. the PR is merged through normal branch protection,
5. the push-triggered `Synthetic Regression Suite` on the resulting main SHA is green,
6. Daily remains PAUSED and no Gemini/Notion Production call is used for this repair.
