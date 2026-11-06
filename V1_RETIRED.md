# AIIF V1 retired from production — 2026-11-06 JST

Owner direction: V1 is no longer needed. Its GitHub Actions operational and CI workflows were removed from the default-branch tree (85 workflow definitions). The **separate** `trendhub-ab/ai-intelligence-factory-next` repository is unaffected.

## Safety / scope
- This is not a deletion of articles, Notion pages, note drafts, credentials or production data.
- Existing history remains recoverable in Git.
- Deleting all default-branch workflow definitions prevents normal V1 GitHub Actions schedules, workflow_dispatch, issue/ChatOps entrypoints, fan-out chains and workflow_run triggers from initiating via the default branch.
- This commit does not stop any already-running job; last inspected V1 in_progress count: 0.
- Other branches or independent external computers/automation cannot be ruled out by repository file changes alone.
- For an organization-level hard shutdown, switch off GitHub Actions for this repository in Settings → Actions → General → Actions permissions; remove any external scheduler/webhook, and revoke V1-only service credentials after confirming Next uses separate credentials.
- Do not re-enable or rerun V1 without a fresh explicit owner decision. This repository should be treated as read-only legacy history.
- Next publication pipeline is not automatically promoted or proven live by this retirement.

## Associated checks
- V1 workflow inventory: 85 YAML definitions as of `main@3276b740c8a525cd47ec9ebe9e6057044137b551`.
- Legacy V1 prompt-audit Draft PR #914 must remain unmerged because it no longer serves the target product.
- New Next development should proceed exclusively in its separate repository.
