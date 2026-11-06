# AIIF V1 retired from production — 2026-11-06 JST

Owner directive: V1 is obsolete. Prevent any V1 production run while keeping the separate AIIF Next repository unchanged.

## Runtime deactivation

- All **81 non-required-CI GitHub Actions workflows** are preserved for history/tests but **every job** has a job-level `if: ${{ false }}` fail-closed guard on the default branch. These include Daily, manual ONE-SHOT, ChatOps, issue reservation, provider/model calls, note drafts, Notion/DB synchronizations, publication reconciliation, member workflows and maintenance jobs. No V1 operational job can run via the default-branch configuration.
- Four **strictly offline safety/CI workflows** stay usable for the protected branch's required status checks:
  `integration-reconciliation-ci.yml`, `p0b-offline-verification.yml`,
  `repository-falsification.yml`, `notion-access-policy-guard.yml`.
  They must not execute V1 production operations.
- Direct legacy Python entrypoints `production_pipeline.main()` and `pipeline.main()` raise `AIIF_V1_RETIRED` before any data production or provider call. There is **no override flag**.

## Preservation and remaining controls

- No article, Notion page, note draft, secret, research data, repository history or Next code is removed by this shutdown.
- Audit-only past V1 PR #914 should remain unmerged; it is superseded by the retirement.
- Last checked running V1 Actions jobs before implementation: zero; a stale September CI job was queued.
- This repository-level stop is not GitHub's **server-side repository Actions disable** setting. Another historical branch may still contain executable workflow code; independent external scripts, schedules and hosts cannot be ruled out by changes to `main` alone.
- For defense-in-depth, disable GitHub Actions in this V1 repository's Settings → Actions → General → Actions permissions (and review all branches) and cancel outstanding V1 runs as appropriate. Stop any external scheduler/webhook, then revoke V1-only credentials once their independence from Next is verified.
- There must be no automatic migration to Next; its production readiness remains a separate decision.

Do not restore any V1 runtime without a fresh explicit owner directive. Treat the V1 repository as legacy read-only history.
