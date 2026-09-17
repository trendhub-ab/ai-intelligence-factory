# Post-merge contract audit implementation plan

**Goal:** Verify merged PR #380 against main, reconcile the reproduced live Source schema drift, and retain only justified historical assets without weakening gates.

**Architecture:** Keep canonical Production behavior and public Notion API authority. Add missing Source options to the three existing schemas, preserve all option IDs/colors, and align new Member DB provisioning with the same Source authority. Execute inline in the existing isolated audit checkout.

**Spec:** User continuation instructions and `AI_Intelligence_Factory_最終仕様書.md`.

## Constraints

- Daily remains PAUSED; no generation calls, historical recovery, note edits or publication.
- Live schema repair is necessary because main Cross DB CI reproduced `情報源 missing=OfficialVendor,X`. Three bounded option-only updates are allowed by the user's necessary-live-verification instruction; no article rows change.
- No Gate, quota, Source allocation, policy rebase or stale-Ready bypass.
- Delete historical assets only after all five user deletion conditions are proven.

## Tasks

- [x] Fetch PR, merge commit, main tree and exact CI/logs. Verify approved head and merged tree match.
- [x] Fetch Technology / Subscriber / Member schemas, add OfficialVendor/X only, re-fetch and compare old option IDs/colors and all unrelated properties. Re-run failed schema job.
- [x] Reproduce Member provisioning incompatibility with a failing test in `tests/test_member_presentation_resolution_guard.py`: normalize generated properties with their Notion `type`, then run `validate_enum_contracts(..., MEMBER_ENUM_CONTRACTS, ...)`.
- [x] Update `provision_member_presentation_db._properties_schema()` to append missing `ACTIVE_PUBLIC_SOURCES` while preserving legacy option order/colors and Unknown. Run the new test and existing Member guards.
- [x] Enumerate all remaining GenRec/RubyGems Python/test/spec assets using exact tracked-file searches and AST import graph from Production and active workflows; record references and retention decisions.
- [x] Compare acquisition, rich-text, PR partition and note diagnostic helper exception/Unicode/limit/hash/DOM contracts. Keep separate unless a bug and safe common contract are demonstrated.
- [x] Verify cap and Telegram trial scopes against runtime layers; document explicit semantics and retain defensive cap.
- [x] Update `docs/audits/2026-09-17-repository-contract-audit.md`, replacing stale Workflow references and distinguishing historical test records from latest results.
- [x] Run full deterministic regression, Synthetic smoke, repository/workflow/Notion guards and Cross DB contract tests. Verify diff and policy hash.
- [ ] Push a follow-up review PR using GitHub Git data tools; verify CI and final main/PR status. Integrate the narrow corrective change and audit documentation after review and Green CI, as required to complete the authorized main audit; verify merged tree and main CI again.
