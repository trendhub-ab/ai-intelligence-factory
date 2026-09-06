# Run255 — Natural Neutralization Fix

Date: 2026-09-06

## Why

Run254 correctly removed unnecessary `自分の` from paid-product copy, but production inspection found a mechanical replacement defect:

- canonical: `自社AIで…`
- Run254 display: `利用環境AIで…`

The copy was subject-neutral, but no longer natural Japanese.

## Fix

Run255 keeps the Work-First / neutral-subject strategy and changes only display normalization.

Broad replacements such as `自社 -> 利用環境` are prohibited. Only context-safe mappings are allowed:

- `自社案件` -> `対象業務`
- `自社要件` -> `利用条件`
- `自社AI` -> `利用中のAI`
- `自社コード` -> `独自コード`
- `自社環境` -> `利用環境`

If a safe semantic mapping is not known, preserve the canonical wording rather than invent an awkward phrase.

## Preserved

- Work-First product purpose
- Neutral-subject Japanese rule
- Client proposal support remains secondary
- Source score / Decision / Evidence unchanged
- Deep Tech inventory unchanged
- Notion schema unchanged
- ZERO model/provider calls
- Daily PAUSED
- Public note release human-only

## Production acceptance

CI green is necessary but not sufficient. After merge, inspect actual Notion records with canonical `自社...` wording and confirm the rendered copy is both meaning-preserving and natural Japanese.
