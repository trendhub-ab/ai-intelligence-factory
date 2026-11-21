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
- Following live Run #44189564875, an additional separately approved `/aiif v04 recover-final 204` command can be used only from the exact prior `OWNER_RECOVERY_ATTEMPTING` state when the owner has confirmed no draft was saved. This final attempt has a **different token**, requires a fresh note-account/list check, rejects observed editor edit routes, validates body HTML conversion before marking `OWNER_FINAL_RECOVERY_ATTEMPTING`, then never retries if uncertain. The v0.4-only `run_v04_note_body_locator.py` validates one below-title body editable and refuses ambiguous/unsafe elements. Non-content stage markers distinguish body discovery, paste and verification failures. This is still **private draft only**, not public release or general-purpose retry.
- When an owner-approved recovery stops because Chrome History contains an edit route, the isolated `run_v04_historical_edit_proof.py` read-only check limits candidates to the exact failed-attempt time window and a single note editor ID. It inspects the authenticated route in a temporary **service-worker-blocked, GET-only** browser context, reads title/body only locally and reports **fixed enums** (not private URLs, IDs or content). More than one candidate fails closed. A navigated edit route alone **does not prove article persistence**. This is advisory and never changes the original ledger, retry authority or publication state.
- **Fresh independent test (2026-11-20):** The owner-only exact `/aiif v04 create 205` command is a separately pinned *one private note draft* dispatch for private Next Issue #205 (`GPT-6.2 Astra Sol`), fixed owner/title/SHA256 `d65a7e9a798f86a31980686483870a1bd6a651ac8f58b12a4fe9ea62427a6650`. It is separate from stuck #204 and uses the same persistent per-issue ledger: **reserve before interacting with note**, reopen/reverify persisted title+body, record verified stable URL, block all ambiguous retries. GitHub Actions checks exact source before starting the dedicated VM. The owner ChatOps command may run only after PR approval+merge; no auto publish or V1 revival. Only one exact creation command is accepted, not general unrestricted submissions.
- V1's three legacy ChatOps workflows remain disabled with `if: ${{ false }}`. This v0.4 ingress requires its own focused zero-model tests and explicit acceptance into the retirement guard. All 81 historical V1 operational jobs remain disabled.

## Proposed separate Next P1.5 read-only VM audit exception

- Pending owner merge and separate live GO, `.github/workflows/p15-persistent-note-ledger-audit.yml` is an **owner-only manual** bridge to read the two existing immutable-content ledgers on the persistent note VM with the already merged **Next P1.5** module (commit `bbf7b49cc4eae1975d3dc838d560c12ccccc3a61`). It is neither a V1 restoration nor a v0.4 draft create/recovery route.
- It uses the **same** `note-draft-create-v2` concurrency group as the independent v0.4 bridge, GCP Workload Identity Federation and the existing `aiif-note-cloud` runner. It rejects an already RUNNING VM, reads only `~/.aiif-note/delivery-ledger-v1.sqlite3` and `~/.aiif-note/v04-private-drafts-v1.json`, and stops a VM started by the audit on completion or most failures.
- No manuscript, note account, Note UI, browser session, Notion page, article delivery ID, Gemini/model API or member asset is modified. Output consists only of fixed status/error codes, aggregate counts and explicit all-false write/publication authority. Ledger scan success is **not** Notion Public API/lineage scan success or permission to retry a failed draft.
- Approval to merge this exception does **not** authorize launching it; running it may start a billed GCP VM and requires separate explicit owner live GO. The retirement guard must continue to reject any new V1 jobs, workflow entrypoints or modifications to the isolated v0.4 bridge. Owner must review branch isolation before merge.

Do not restore any V1 runtime without a fresh explicit owner directive. Treat all historical V1 operations as retired; only the separately enumerated v0.4 owner-only exceptions remain executable.
