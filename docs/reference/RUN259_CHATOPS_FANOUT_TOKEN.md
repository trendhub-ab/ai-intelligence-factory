# Run259 — ChatOps Fan-out Token Integrity

Date: 2026-09-06

## Problem observed in Production

A full ONE-SHOT was requested from the dedicated ChatOps control issue and `Daily Intelligence & Content Pipeline [ONE-SHOT]` completed successfully. The expected downstream `workflow_run` fan-out did not create new `Note Ready Article Sync` / `Subscriber Decision Brief Sync` runs.

The ChatOps bridge authenticated its `workflow_dispatch` request with the repository-scoped `github.token` / `GITHUB_TOKEN`.

## Root cause

GitHub Actions suppresses most workflow-triggering events created with a workflow's repository `GITHUB_TOKEN` in order to prevent recursive automation. `workflow_dispatch` itself is an allowed exception, so the ONE-SHOT starts, but a workflow dispatched from another workflow with that token is not a reliable source for the intended subsequent `workflow_run` chain.

This repository already carries `GH_PAT` into Production ONE-SHOT execution. Run259 changes only the ChatOps dispatch authentication so the ONE-SHOT is created under a chainable credential.

## Change

`.github/workflows/chatops-one-shot.yml`

- `GH_TOKEN` for the dispatch step is now `${{ secrets.GH_PAT }}`.
- There is no fallback to `${{ github.token }}`.
- Empty/missing `GH_PAT` fails closed before dispatch.
- Existing exact owner / issue #71 / exact command / `RUN_ONCE` authorization remains unchanged.
- The bridge still never runs Production directly.
- Scheduled Daily remains hard-PAUSED.
- Public note release remains human-only.

## Downstream contract preserved

The existing downstream workflows remain unchanged:

- `Note Ready Article Sync` subscribes to successful `Daily Intelligence & Content Pipeline [ONE-SHOT]` completion on `main`.
- `Subscriber Decision Brief Sync` subscribes to successful `Daily Intelligence & Content Pipeline [ONE-SHOT]` completion on `main` and retains the Inventory `[apply]` rule.

## Regression coverage

- `tests/test_run202_chatops_control.py`
  - asserts ChatOps uses `secrets.GH_PAT`
  - rejects `github.token` as dispatch credential
  - asserts missing PAT fails closed
- `tests/test_run259_chatops_fanout_token.py`
  - locks the PAT dispatch contract
  - locks both downstream ONE-SHOT subscriptions
  - verifies the fix does not resume Scheduled Daily or add public note release automation

## Non-changes

Run259 does not modify:

- `production_pipeline.py`
- Gemini model selection, request budgets, RPD/RPM/TPM guards, or retry budgets
- Fact / Evidence / Decision gates
- Notion schema or canonical IDs
- note public-release policy
- Scheduled Daily state

## Operator rule

ChatOps ONE-SHOT execution requires a repository secret named `GH_PAT` with permission to dispatch Actions in this repository. If that secret is missing or invalid, ChatOps must fail closed rather than silently using `GITHUB_TOKEN` and creating a partial full-set execution with no downstream fan-out.
