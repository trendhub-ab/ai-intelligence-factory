# AIIF V1 retired from production — 2026-11-06 JST

Owner directive: V1 is obsolete. Prevent any V1 production run while keeping the separate AIIF Next repository unchanged.

## Runtime deactivation

- All **81 legacy V1 operational GitHub Actions workflows** are preserved for history/tests but **every job** has a job-level `if: ${{ false }}` fail-closed guard on the default branch. These include Daily, manual ONE-SHOT, ChatOps, issue reservation, provider/model calls, note drafts, Notion/DB synchronizations, publication reconciliation, member workflows and maintenance jobs. No V1 operational job can run via the default-branch configuration.
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

## Isolated v0.4 exceptions (not a V1 revival)

- `v04-single-note-draft-bridge.yml` remains the independently authorized, single-owner manual private-draft workflow. It retains strict `ATTEMPTING` anti-replay authority, account verification and no public release.
- `v04-owner-chatops-inspect.yml` is the *one* separately authorized owner-only `issue_comment` exception on control Issue #71. It accepts only `/aiif v04 inspect 204` or the distinct `/aiif v04 recover 204` command, revalidates the event in Python, and claims each comment once. Both pin private source Issue #204 and SHA256. Inspect is read-only. Recover requires a separate exact owner confirmation token, verified note account, negative bounded official list scan, eligible historical route evidence and an older `ATTEMPTING` ledger with no known draft URL. It permanently consumes a single recovery opportunity before opening the editor; it does not permit blind retries, publication, Gemini or V1 Production. Owner's absent-draft confirmation is supporting evidence rather than server-side proof of nonexistence.
- V1's three legacy ChatOps workflows remain disabled with `if: ${{ false }}`. This v0.4 ingress requires its own focused zero-model tests and explicit acceptance into the retirement guard. All 81 historical V1 operational jobs remain disabled.

Do not restore any V1 runtime without a fresh explicit owner directive. Treat all historical V1 operations as retired; only the separately enumerated v0.4 owner-only exceptions remain executable.
