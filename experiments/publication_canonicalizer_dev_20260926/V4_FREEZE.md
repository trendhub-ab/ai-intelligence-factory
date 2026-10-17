# Publication Canonicalizer v4 — Freeze

Status: **FROZEN CANDIDATE — NOT PRODUCTION READY**

- Canonicalizer v4 blob: `414089a14c238f104b2866507ddf8521c2baf420`
- Local Writer v3 blob: `dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2`
- Validated code head: `f4925ee2d930330676b9e35162faa0cf2cad82a0`
- Integration run: `36186090527`

## Frozen v4 contract

v4 adds one narrow capability to v3: deterministic scope preservation for source-side performance multipliers.

It may annotate a multiplier only when the same multiplier exists in the structured source surface and its local source context carries benchmark / measurement / expectation / trial / example modality. It never changes the multiplier or any numeric lexeme. It adds only a conservative scope marker and, when absent, a variability caveat stating that real improvement can vary with workload, conditions, and execution environment.

The transform is idempotent. Evidence, Decision, score, canonical entity identity, and evidence URLs are preserved.

## Regression state

- Stage 4 development set: **8/8**
- Stage 5 contaminated repair regression: **4/4**
- Stage 5 original blind result remains **3/4** and is not reinterpreted.
- Full deterministic regression: **2,935 passed / 1 warning / 0 failed**
- Production synthetic smoke: **30/30**
- critical_failures: **0**
- production_write_isolation: **true**

## Methodological boundary

The 4/4 Stage 5 repair regression is not validation because Stage 5 was already observed before v4 was designed. Production readiness requires a new untouched holdout. Do not reuse Stage 3, Stage 4, or Stage 5 samples for that claim, and do not weaken evidence eligibility to manufacture a test set.

Do not merge. Do not publish. Do not enable in Production until a fresh holdout validates this exact blob.
