# Run119 Evidence Entity Binding Gate Validation — 2026-08-24

## Business decision
Run118 authority typing correctly separated discovery/secondary sources, but live Evidence Ledger audit found an authority-integrity defect: an official domain could be classified as decision-eligible even when it was not first-party evidence *for the assessed Technology*. Examples included Replicate arXiv docs attached to unrelated arXiv papers and an OpenAI guide attached to a curated GitHub list.

Run119 therefore makes paid decision authority the conjunction of source authority and deterministic entity binding. No new Gemini call is introduced.

## Binding logic
- GitHub entity: exact `owner/repo` URL is `IDENTITY_ANCHOR`.
- GitHub external docs/site: eligible only when the host is tied to explicit repository metadata (homepage/docs/official URL); a random README external link is not enough.
- arXiv entity: only the exact paper id on arXiv is `IDENTITY_ANCHOR`; unrelated DOI/Zenodo/Replicate pages remain auditable but are `UNBOUND` by default.
- Product Hunt / Hacker News / web entities: resolved non-discovery primary site can bind evidence on that same site.
- Regulatory evidence can bind only when a deterministic entity token is present in the evidence extract.
- Secondary news and discovery sources remain ineligible regardless of binding.
- If binding cannot be proven, fail closed: `Decision Evidence Eligible=false`.

Ledger adds `Entity Binding` and `Entity Binding Reason`. Historical snapshots remain append-only; a zero-Gemini backfill creates fresh snapshots and deactivates prior snapshots for the same entity/live URL.

## Falsification
Run119 dedicated tests: 10/10 PASS.
Mutation negative control: 3/3 KILLED:
1. UNBOUND evidence promoted to eligible.
2. Any GitHub repository treated as the assessed repository.
3. External arXiv-related URL treated as the same paper.

## Full regression
- unittest: 573/573 PASS
- pytest: 573 passed + 19 subtests PASS
- Synthetic Full: 500/500 PASS
- critical failures: 0
- major failures: 0
- compileall: PASS
- production `_generate_via_chat(` call sites: 7 (unchanged)
- production `genai.Client` sites: 2 (unchanged)

## Deployment order
1. Deploy Run119.
2. Keep `EVIDENCE_LEDGER_REQUIRED=false`.
3. Run Evidence Ledger Maintenance `migrate-schema` once; this adds the two binding columns idempotently and does not call Gemini.
4. Run `dry-run`, limit 20.
5. Run `backfill`, limit 20. This supersedes current active snapshots with entity-bound classifications, zero Gemini.
6. Re-run Technology-level coverage audit. Require all assessed launch-inventory Technologies to have at least one active `Decision Evidence Eligible=true` snapshot with `Entity Binding` not UNBOUND/UNKNOWN.
7. Only then set `EVIDENCE_LEDGER_REQUIRED=true`.
