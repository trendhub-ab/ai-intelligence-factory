# Notion Access Policy

## Purpose

Prevent AI Intelligence Factory operations from depending on Notion MCP SQL quotas.
The production system must remain operable on the Notion Public API and saved Notion views.

## Default access order

1. Fetch the database/data-source schema.
2. Use an existing saved Notion view for routine audits and filtered reads.
3. Use Notion workspace search/fetch for targeted inspection.
4. Use the Notion Public API with pagination for production automation, completeness checks, dedupe checks, and row-level audits.
5. Do not use Notion MCP SQL as a production dependency.

## MCP SQL rule

Notion MCP `query_data_sources` SQL mode is prohibited in production/runtime code.
It may only be used as an exceptional operator-side investigation when explicitly justified and when the workspace plan supports it. No workflow, guard, sync, or product feature may require MCP SQL to function.

The repository-level `notion_access_policy_guard.py` fails closed if production Python or GitHub workflow files introduce known MCP SQL call patterns.

## Routine audits that should use saved views

### Content Intelligence DB

- `監査｜Ready記事`
- `監査｜Ready必須欠落`
- `監査｜要編集`

### Clean member presentation DB

- `監査｜必須項目欠落`

### note posting DB

- `監査｜Ready取消`

## Audits that require aggregation or duplicate detection

Use the existing Python/Public API path:

- paginate all relevant rows through Notion Public API;
- aggregate in Python;
- validate duplicates and missing fields locally;
- keep requests bounded and retry/backoff on HTTP 429;
- never convert these checks into MCP SQL dependencies.

Existing examples include `cross_db_contract_guard.py`, `content_db_contract_guard.py`, `evidence_db_contract_guard.py`, `member_presentation_sync.py`, and `note_ready_sync.py`.

## Cost and reliability principle

The goal is not to maximize Notion query sophistication. The goal is to keep member/product operations reliable at the lowest recurring cost. Saved views and Public API reads are the default; SQL quota should not be part of normal operations.
