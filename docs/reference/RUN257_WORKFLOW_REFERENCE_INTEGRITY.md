# Run257 — Workflow Reference Integrity

Date: 2026-09-06 JST  
Scope: GitHub Actions static execution references / paused-Daily downstream fan-out  
Provider calls: **0**

## Why this Run exists

After Run256 was merged, the repository was re-audited under the assumption that another program or stale edit might have touched GitHub data. Existing CI proved runtime and product behavior, but it did not fail closed on every static GitHub Actions reference.

Run257 adds a repository-local reference guard and uses it to audit the current workflow graph before changing anything.

## Observed findings

The first guard execution reported 23 findings.

- 21 were guard false positives: `python -m unittest discover -s tests -p 'test_x.py'` selectors were initially interpreted as repository-root executable paths.
- 2 were real dangling `workflow_run` upstream references:
  - `.github/workflows/note-ready-sync.yml`
  - `.github/workflows/subscriber-decision-brief.yml`
- Both referenced `Daily Intelligence & Content Pipeline`, but the actual scheduled workflow is currently named `Daily Intelligence & Content Pipeline [PAUSED]` and is hard-disabled.
- The real manual production path remains `Daily Intelligence & Content Pipeline [ONE-SHOT]`.
- The previously suspected `subscriber-decision-brief.yml -> run182_client_facing_nomination.py` reference is **not present** in current main and required no repair.

## Repair

While scheduled Daily remains PAUSED:

- `Note Ready Article Sync` follows the real ONE-SHOT workflow only.
- `Subscriber Decision Brief Sync` follows the real ONE-SHOT workflow plus `Subscriber Inventory Bootstrap`; Inventory plan remains read-only and only `[apply]` may fan out into member writes.
- Neither downstream workflow subscribes to the hard-paused stub.
- Neither workflow keeps a nonexistent future alias as a live `workflow_run` source.
- When scheduled Daily is explicitly resumed, its then-current real workflow name must be re-added deliberately in the same reviewed change.

No provider calls, Notion schema changes, Decision/Evidence changes, article-quality changes, or public-note automation changes are introduced by this repair.

## New fail-closed guard

`workflow_reference_guard.py` validates repository-local static references across all files in `.github/workflows/`:

- `.py` / `.sh` paths referenced from `run:` and `- run:` blocks
- `python -m unittest tests.*` module paths
- local actions referenced by `uses: ./...` and `- uses: ./...`
- `workflow_run.workflows` upstream workflow names
- static `gh workflow run` targets
- duplicate top-level workflow names

Dynamic/external commands are not guessed. `unittest discover -p` selectors are treated as selectors under their start directory rather than repository-root executable paths.

CI: `.github/workflows/workflow-reference-guard.yml`.

## Regression contract

`tests/test_workflow_reference_guard.py` covers:

- valid references
- missing scripts
- missing unittest modules
- missing upstream workflow names
- missing local actions
- missing `gh workflow run` targets
- `unittest discover -p` false-positive prevention
- the current repository itself

Existing Run194 and Run211 regressions are updated to lock the paused-Daily behavior explicitly instead of assuming a non-existent normal-Daily workflow name.

## Safety / merge rule

- Daily remains **PAUSED**.
- Public note publication remains human-only.
- Old Runs are not deleted merely because they are old.
- Existing tests/guards are not weakened to green the PR.
- Merge only after Workflow Reference Guard, Repository-wide Falsification Guard, Integration Reconciliation CI (including full pytest + Synthetic Production), and relevant access/sync guards are green on the final head.
