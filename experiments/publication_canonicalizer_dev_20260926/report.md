# Stage 4 — Publication Canonicalizer Development Result

## Result

The separate 8-record development set improved from **1/8** with frozen Local Writer v3 alone to **8/8** with deterministic Publication Canonicalizer v3.

- Baseline: **1/8**
- Canonicalizer intermediate: **6/8**
- Canonicalizer v3: **8/8**
- Gemini / OpenAI / other LLM API calls: **0**
- Production changes: **none**
- Gate changes: **none**
- Notion writes: **none**
- note publication: **none**
- Stage 3 holdout reused for tuning: **false**

## What the Canonicalizer does

It sits before the frozen Local Writer:

`Structured Record → Publication Canonicalizer → Local Writer v3 → existing Gates`

The Canonicalizer is Pure Python and deterministic. Its responsibilities are limited to publication contracts:

1. normalize title terminal punctuation required by Fact Gate;
2. neutralize unsupported exclusivity / hype / market-standard wording without strengthening claims;
3. add bounded first-use terminology bridges for already-present technical terms;
4. constrain low-score / WATCH / WAIT / AVOID actions to limited verification language;
5. use a canonical presentation seed rather than a storage-specific Notion page ID for layout diversification;
6. preserve the original structured record as the evidence context for Fact validation.

It does **not** create Evidence, alter Decision/Score, modify URLs, relax Gates, or generate new performance claims.

## Development sequence

The first Canonicalizer pass reached **6/8**. The remaining failures were diagnostic:

- one Reader Value failure where a term was explained in summary state but not independently in the article body;
- one Fact boundary failure where an explanatory glossary accidentally introduced the named fact `Windows`, which was absent from the evidence.

v3 fixed those generically by separating summary/body glossary state and removing the unsupported named fact from the glossary definition.

## Final CI

Successful Integration run: **36182081140**

- Full deterministic regression: **2,931 passed / 1 warning / 0 failed**
- Production synthetic smoke: **30/30 passed**
- critical_failures: **0**
- production_write_isolation: **true**

## Interpretation

Stage 3 showed that Local Writer v3 alone did not generalize to untouched structured records. Stage 4 shows that, on a separate development set, the missing layer can be implemented as a deterministic publication compiler rather than another LLM call.

This is encouraging but is **not yet Production proof** because the 8 records were a development set used to refine the Canonicalizer.

## Next experiment

Freeze Publication Canonicalizer v3 and Local Writer v3, then evaluate them without modification on a **new untouched holdout**. Do not reuse the Stage 3 holdout or any Stage 4 development record for tuning.

Draft / Do not merge.
