# Run258 — Required Workflow Reference Guard

Date: 2026-09-06 JST  
Scope: make Run257 Workflow Reference Integrity part of an already-required merge gate  
Provider calls: **0**

## Why this Run exists

Run257 repaired two real dangling `workflow_run` references and added the standalone `Workflow Reference Guard`. Post-merge verification then checked the repository ruleset `Protect main production`.

The ruleset is active on the default branch and requires PRs, blocks deletion/non-fast-forward updates, has no bypass actors, and requires these status contexts:

- `zero-api-regression`
- `falsify-all-tracked-surfaces`
- `notion-access-policy`

The standalone Run257 `Workflow Reference Guard` was green, but its own status context was not one of the ruleset-required checks. That left an avoidable gap: a future PR could theoretically merge while the standalone reference guard was red if the three existing required contexts remained green.

## Repair

Without changing repository administration settings, Run258 makes the Run257 guard part of the already-required `falsify-all-tracked-surfaces` job in `.github/workflows/repository-falsification.yml`.

That required job now:

1. compiles `workflow_reference_guard.py`,
2. runs `python workflow_reference_guard.py`,
3. runs `python -m unittest tests.test_workflow_reference_guard -v`.

`tests/test_workflow_reference_guard.py` also asserts that the required repository-falsification workflow continues to invoke both the guard and its regression suite.

## Safety

- Daily remains **PAUSED**.
- No Gemini/model calls are added.
- No Notion schema or customer data contracts are changed.
- No Decision/Evidence/Source Score/Deep Tech behavior is changed.
- Existing required status context names remain unchanged, so the active repository ruleset does not need to be edited.
- Public note publication remains human-only.

## Verification / merge rule

Merge only if the final head is green for:

- `falsify-all-tracked-surfaces` including the new Run257 reference step,
- `zero-api-regression`,
- `notion-access-policy`,
- standalone Workflow Reference Guard,
- full Integration/Synthetic checks triggered by the repository.
