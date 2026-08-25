# Run119 Evidence Entity Binding Setup

Use the existing Evidence Ledger database. Do not create a second database.

1. Deploy Run119 to `main`.
2. Leave `ENABLE_EVIDENCE_LEDGER=true` and `EVIDENCE_LEDGER_REQUIRED=false`.
3. Run **Evidence Ledger Maintenance** with `mode=migrate-schema`, `limit=20`. It adds `Entity Binding` and `Entity Binding Reason` idempotently; Gemini calls remain zero.
4. Run `mode=dry-run`, `limit=20`.
5. If failed=0 and zero_gemini_calls=true, run `mode=backfill`, `limit=20`.
6. Audit active snapshots at Technology level. Required condition: every assessed launch-inventory Technology has >=1 active decision-eligible evidence with deterministic entity binding.
7. Only after that set `EVIDENCE_LEDGER_REQUIRED=true`.

Do not manually delete the existing 34 snapshots. Run119 backfill creates new append-only snapshots and deactivates older active snapshots for the same entity/live URL, preserving audit history.
