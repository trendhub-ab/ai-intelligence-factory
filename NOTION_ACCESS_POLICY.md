# Notion Access Policy

## Purpose

Prevent AI Intelligence Factory operations and operator audits from depending on Notion MCP SQL quotas.
Every production Notion database must have a SQL-free audit path.
The production system must remain operable on the Notion Public API and saved Notion views.

## Default access order

1. Fetch the database/data-source schema.
2. Use a registered saved Notion view for routine audits and filtered reads.
3. Use Notion workspace search/fetch for targeted inspection.
4. Use the Notion Public API with pagination for production automation, completeness checks, dedupe checks, row-level audits, and secret-only destinations.
5. Do not use Notion MCP SQL as a production or routine audit dependency.

## MCP SQL rule

Notion MCP `query_data_sources` SQL mode is prohibited in production/runtime code and routine operator audits.
It may only be used as an exceptional one-off investigation when explicitly justified and when the workspace plan supports it. No workflow, guard, sync, product feature, or standard audit may require MCP SQL to function.

The repository-level `notion_access_policy_guard.py` fails closed if production Python or GitHub workflow files introduce known MCP SQL call patterns or if a production DB disappears from the registered SQL-free audit manifest.

## Source of truth for all SQL-free audit paths

`notion_audit_views.json` registers every production Notion DB and its SQL-free audit method.
A DB may use:

- `view+public_api`: saved Notion views for routine inspection plus Public API for aggregation/dedupe; or
- `public_api`: Public API only when the destination ID is intentionally held in GitHub Secrets.

## Registered databases and routine audits

### Content Intelligence DB

- `監査｜Ready記事`
- `監査｜Ready必須欠落`
- `監査｜要編集`

### Technology Intelligence DB

- `監査｜評価済み必須欠落`
- `監査｜エンティティ未解決`

`評価済み必須欠落` only audits `評価状態=ASSESSED`, so legacy/unassessed rows are not misclassified as broken.

### Decision History DB

- `監査｜履歴必須欠落`

INITIAL snapshots are not required to have a previous score/status. The audit checks only fields that every real history event must carry.

### Subscriber bridge / AI Decision Intelligence

- `監査｜会員同期必須欠落`

The audit is limited to rows that already have an adoption decision, so legacy seed rows are not treated as member-sync failures.

### Clean member presentation DB

- `監査｜必須項目欠落`

### Decision Monthly DB

- `監査｜月次必須欠落`

### Evidence Ledger

- `監査｜有効根拠必須欠落`
- `監査｜利用根拠ソース異常`
- existing `要対応｜再レビュー`

`有効根拠必須欠落` is intentionally restricted to `有効スナップショット=YES`. Older usable-but-inactive evidence snapshots may legitimately lack newer binding metadata.

### note posting DB

- `監査｜Ready取消`

### Secret-configured Public mirror DB

The Public mirror destination is configured through `NOTION_PUBLIC_DATABASE_ID` / `NOTION_PUBLIC_DATA_SOURCE_ID` GitHub Secrets, so a stable workspace view ID is not stored in the repository.

Its SQL-free audit path is `public_db_contract_guard.py`, which uses only the Notion Public API and validates:

- destination schema has exactly one title property;
- `元情報URL` exists as URL type;
- URL-managed rows have nonblank titles;
- canonical `元情報URL` values are unique;
- manually added rows without `元情報URL` remain allowed, matching the reconciliation policy.

`.github/workflows/public-db-sync.yml` runs this guard after every Public mirror sync.

## Audits that require aggregation or duplicate detection

Use the existing Python/Public API path:

- paginate all relevant rows through Notion Public API;
- aggregate in Python;
- validate duplicates and missing fields locally;
- keep requests bounded and retry/backoff on HTTP 429;
- never convert these checks into MCP SQL dependencies.

Existing examples include `cross_db_contract_guard.py`, `content_db_contract_guard.py`, `evidence_db_contract_guard.py`, `member_presentation_sync.py`, `note_ready_sync.py`, and `public_db_contract_guard.py`.

## Cost and reliability principle

The goal is not to maximize Notion query sophistication. The goal is to keep member/product operations reliable at the lowest recurring cost. Saved views and Public API reads are the default; MCP SQL quota is not part of normal operations.
