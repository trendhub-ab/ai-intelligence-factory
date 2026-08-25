# Run118 Evidence Authority Classification Validation

Date: 2026-08-24

## Goal
Extend Run117 Evidence Ledger beyond GitHub/arXiv examples so every retrieved evidence URL is classified by authority. Discovery/secondary news can remain auditable, but cannot independently satisfy paid Decision Intelligence primary-authority requirements.

## Implemented taxonomy
Source Type:
- GITHUB
- ARXIV
- OFFICIAL_DOCS
- OFFICIAL_BLOG
- OFFICIAL_CHANGELOG
- OFFICIAL_SITE
- AUTHOR_ORIGINAL
- INTERVIEW_PRIMARY
- REGULATORY
- SECONDARY_NEWS
- DISCOVERY
- OTHER_PRIMARY
- SUPPLEMENTAL
- UNKNOWN

Authority Class:
- PRIMARY_FIRST_PARTY
- PRIMARY_REGULATORY
- PRIMARY_AUTHOR
- PRIMARY_INTERVIEW
- PRIMARY_OTHER
- SECONDARY
- DISCOVERY
- UNKNOWN

Decision Evidence Eligible is stored independently as a checkbox.

## Business rule
- Hacker News and Product Hunt remain discovery channels by default.
- Known secondary-news hosts are never promoted merely because retrieval succeeded or role was labelled PRIMARY_SOURCE.
- Resolved official docs/site/changelog/blog, GitHub, arXiv, regulatory sources, and qualified author-original/interview evidence may be decision eligible.
- Supplemental evidence cannot independently establish primary authority.
- Classification is deterministic and zero-Gemini.
- Existing Fact/Evidence/Relation/Numeric gates remain in force; decision-eligible is necessary authority metadata, not a bypass.

## Run117 Ledger migration
Three internal-only columns were added:
- Authority Class (RICH_TEXT)
- Decision Evidence Eligible (CHECKBOX)
- Authority Reason (RICH_TEXT)

`Evidence Ledger Maintenance` now supports `migrate-schema`, which idempotently adds these columns to an existing Run117 Evidence Ledger through Notion's data-source schema API. No subscriber DB schema changes are required.

## Falsification
Dedicated Run118 tests: 12/12 PASS.

Key cases:
- GitHub/arXiv primary accepted.
- HN/Product Hunt discovery rejected as authority.
- Reuters/TechCrunch-style secondary news rejected even if labelled PRIMARY_SOURCE.
- Official docs/blog/changelog/regulatory typed and eligible.
- HN external author-original retained where existing semantics permit it.
- Product Hunt external official site accepted.
- Supplemental evidence cannot independently raise authority.
- HN discovery + retrieved official docs passes authority.
- Secondary-only HN evidence fails authority.
- Ledger persists authority metadata without altering Decision Score.
- Authority summary counts only eligible documents.
- Schema migration is idempotent.

Mutation negative control: 3/3 KILLED.
- secondary news promotion mutation
- discovery promotion mutation
- supplemental promotion mutation

## Full regression
- unittest: 563/563 PASS
- pytest: 563 passed + 19 subtests PASS
- Synthetic Full: 500/500 PASS
- critical: 0
- major: 0
- production_write_isolation: true

## External API compatibility check
Notion official documentation for API version 2026-03-11 confirms data-source schema changes use PATCH `/v1/data_sources/{data_source_id}` with a `properties` body. Run118's idempotent migration follows that contract.
