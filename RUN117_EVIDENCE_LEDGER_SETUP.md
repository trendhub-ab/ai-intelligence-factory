# Run117 Evidence Ledger Setup

## 1. Create the internal Notion database

Create one private internal database named `Evidence Ledger` with this schema:

```sql
CREATE TABLE (
  "Evidence Record" TITLE,
  "Technology Entity ID" RICH_TEXT,
  "Technology Page ID" RICH_TEXT,
  "Evidence URL" URL,
  "Immutable Evidence URL" URL,
  "Resolved URL" URL,
  "Source Version" RICH_TEXT,
  "Source Type" RICH_TEXT,
  "Evidence Role" RICH_TEXT,
  "Retrieved At" DATE,
  "Last Verified At" DATE,
  "Source Health" SELECT('VERIFIED':green, 'COSMETIC_CHANGE':yellow, 'MOVED':blue, 'MATERIAL_CHANGE':orange, 'MISSING':red, 'FETCH_ERROR':gray),
  "Document Hash" RICH_TEXT,
  "Extract Hash" RICH_TEXT,
  "Evidence Extract" RICH_TEXT,
  "Evidence Identity" RICH_TEXT,
  "Active Snapshot" CHECKBOX,
  "Re-review Triggered" CHECKBOX,
  "Authority Class" RICH_TEXT,
  "Decision Evidence Eligible" CHECKBOX,
  "Authority Reason" RICH_TEXT
)
```

Use the same Notion integration/token as the internal Decision Intelligence DB, and grant that integration access to this database.

## 2. GitHub Secrets / Variables

Secrets:
- `NOTION_EVIDENCE_DATABASE_ID`
- `NOTION_EVIDENCE_DATA_SOURCE_ID`

Variables:
- `ENABLE_EVIDENCE_LEDGER=true`
- initially `EVIDENCE_LEDGER_REQUIRED=false`

The existing `NOTION_DECISION_INTELLIGENCE_API_KEY` is reused. No new Gemini key or model budget is required.

## 3. Backfill existing assessed inventory

Use the new GitHub Actions workflow `Evidence Ledger Maintenance`.

First:
- mode: `dry-run`
- limit: `20`

Then, after checking the output:
- mode: `backfill`
- limit: `20`

Backfill uses zero Gemini. It rehydrates current first-party evidence and stores a snapshot timestamped at the backfill run. It does **not** claim to reconstruct evidence content from before Run117.

## 4. Required mode

Once all currently subscriber-visible assessed records have at least one valid active snapshot, set:

`EVIDENCE_LEDGER_REQUIRED=true`

From that point, a new Decision Intelligence assessment cannot be treated as safely persisted if no evidence snapshot can be created.

## 5. Daily behavior

Daily automatically checks up to 20 oldest active snapshots with zero Gemini. `MATERIAL_CHANGE` or `MISSING` only accelerates `Next Review`; the normal Product Review scheduler decides when Gemini is actually spent.


## Run118 authority migration

If the Evidence Ledger was already created with the Run117 schema, run the `Evidence Ledger Maintenance` workflow once with:

- mode: `migrate-schema`

This is idempotent and adds only `Authority Class`, `Decision Evidence Eligible`, and `Authority Reason`. Then run `dry-run` and `backfill` as before. No subscriber-facing database columns are added.
