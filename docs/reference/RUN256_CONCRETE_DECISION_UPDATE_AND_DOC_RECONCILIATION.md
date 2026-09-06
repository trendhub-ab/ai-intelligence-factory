# Run256 — Concrete Decision Update + Documentation Reconciliation

Date: 2026-09-06

## Why

Run250–255 rebuilt the paid member surface, but two gaps remained:

1. The monthly Brief described Decision Update abstractly without surfacing a concrete current example.
2. `AI_Intelligence_Factory_最終仕様書.md` still described the older note-membership / DB+Digest product and had not caught up with the Work-First product contract.

## Product change

When a material change exists and is relevant to work-use judgment, the monthly Decision Brief must surface at least one concrete update in the body. A generic database link is not enough.

If no relevant material change exists, the Brief must explicitly say that there is no important judgment change rather than inventing one.

### September 2026 example

`FlowiseAI/Flowise` is used as the concrete Decision Update:

- Official GitHub repository is Archived.
- Current member judgment is AVOID for new adoption.
- Existing Flowise use is treated as maintenance/migration context.
- Next action is to compare currently maintained alternatives.

The archived state was rechecked directly against the official GitHub repository before adding the Brief item.

## Documentation change

`AI_Intelligence_Factory_最終仕様書.md` was slimmed from a historical accumulation into a current Production contract.

The new document:
- points to current code/tests as authority,
- uses `PAID_PRODUCT_CONTRACT.md` as the paid-product detail contract,
- records Work-First / neutral-subject product semantics,
- removes the obsolete assumption that note itself is the market,
- does not claim an unverified payment provider as Production-complete,
- preserves Daily PAUSED, human-only public release, Evidence/Decision/Deep Tech, zero-provider-call presentation rules,
- keeps detailed old Run rationale in `docs/reference/` and Git history rather than growing the final spec indefinitely.

## Safety

Documentation / editorial product change only.

- No canonical Decision mutation
- No source score mutation
- No Evidence weakening
- No Deep Tech deletion
- No Notion schema change
- No new provider calls
- Daily remains PAUSED
- Public note release remains human-only
