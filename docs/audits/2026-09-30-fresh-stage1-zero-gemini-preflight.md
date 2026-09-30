# Stage 1 — Fresh source preflight without Gemini (2026-09-30)

## Entry and safety
A separate **manual** workflow, `Fresh Source Preflight [ZERO GEMINI]`, requires `RUN_READ_ONLY_PREFLIGHT`. It checks out current main and enters `production_pipeline.py` in the isolated `local_skills_source_preflight` mode before model runtime initialization and font fetching. The runner receives **no Gemini API key**. It retains normal Production source-acquisition overlays, legal gate, identity dedupe, existing-Notion lookup and shared screening ceiling; it never invokes Screening, Calibration, Deep Dive, Local Skills Writer, quality Gates, note synchronization, or Notion article persistence.

This is **zero Gemini/LLM usage, not zero internet/API usage**: it reads GitHub, HN, arXiv, official vendor sources and the authoritative Notion dedupe index. Do **not** run it while source/Notion rate limits are also constrained. No automatic schedule or ChatOps command is introduced.

The private `fresh-source-zero-gemini-<run number>` artifact contains aggregate counts only: collected, current round-robin membership, legal-safe, dedupe exclusion (existing Notion and intra-run causes separately), already-observed holdout exclusion, and remaining Fresh count for each active source. It contains no candidate titles, source URLs, secrets, score guesses or article text. Source preflight refuses missing GitHub/Notion credentials and also refuses a Gemini credential.

## Interpretation
`NO_FRESH_CANDIDATES` means a source has no candidates after *current* acquisition/legal/dedupe. `FRESH_PRE_SCREEN_ONLY` means only that at least one candidate survives; it does **not** prove the Production score threshold, source preflight, Evidence sufficiency, Gate passage or publication value.

This preflight is not a new Fresh run and cannot count as source-stratified 4/4. The existing #654 1/4 measured PASS plus three UNMEASURED remains unchanged.

## Future experiment gate
Stage 2 must record a separate proposed source-acquisition protocol before changing any collection query, screening threshold or source-selection order. Stage 3 must freeze the final Writer/Canonicalizer/Gate/selection fingerprint, per-run API-call allowance, 503 stop condition, and original holdout exclusions before resuming any real Fresh measurement. No model/API-consuming runs were made to build or test this implementation.
