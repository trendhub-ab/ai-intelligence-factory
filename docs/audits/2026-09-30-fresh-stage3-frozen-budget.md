# Stage 3 — Fresh 0/4 source-stratified budget and runtime preregistration

**Registered:** 2026-09-30, BEFORE any new live source preflight or Fresh provider send.
**Prior audited result:** v4.3.9 mixed-source Fresh 4/4 on HackerNews-discovered articles; the *separate* original four-source campaign is **1/4** (HackerNews PASS, GitHub/ArXiv/OfficialVendor UNMEASURED).
**New campaign status:** **PREREGISTERED / ZERO NEW MEASUREMENTS (0/4)**. The prior 1/4 is historical evidence, not carried into this new campaign.
**Baseline main:** `f149bda8c176dd0a9997d89396b0acee0f0d1611`. Guard: `fresh_campaign_lock.py`.

## Frozen measurement subject

Keep existing Local Skills v4.3.9-integrated Writer Git blob `884c550125ff563b2d8bcf20132f3373d332f28d`, Canonicalizer `93a62ef2311d43dc1cb84fa5affe9d798a133021`, Evidence Boundary `stage10-v4`, current source/Notion dedupe, Screening/Calibration/Deep Dive selection, and all Fact, Editorial, Publication and Human Appeal Gates and thresholds unchanged. The runtime lock validates baseline Python tree changes and key blob fingerprints BEFORE source or Gemini sends. This stage only adds a canary-only guard and explicit workflow confirmation.

**Discovery:** GitHub/HackerNews/ArXiv/OfficialVendor, one untouched candidate per exact discovery source. Prior inspected titles/primary URLs remain quarantined. Use unchanged **baseline** Production acquisition, 50 per source/200 screening total, with no source substitution. Stage-2 three-cohort GitHub widening is **a separate zero-Gemini experiment**; it cannot be silently mixed into this registered baseline Fresh. If it is later adopted, register a different acquisition fingerprint and NEW 0/4 campaign before any provider measurement.

## Registered Gemini budget / stop rules

- This is the provider-assisted **structured-data** stage; Local Skills article rendering itself makes **zero** Gemini requests.
- Per one source-specific run: **6 total provider send attempts across Screening, Calibration and Deep Dive**, including failed responses, retries and fallbacks. **One** Deep Dive send maximum, including failed sends/fallbacks. The first prospective over-budget send is stopped before contacting the provider.
- Screening pool fixed: `gemini-3.5-flash-lite,gemini-3.1-flash-lite`. Deep Dive pool fixed: `gemini-3.7-flash,gemini-3.8-flash,gemini-3.6-flash,gemini-3.5-flash`. Current dynamic health-aware routing within these pools is retained; no new models, run-scoped exclusions, additional retries, calibration bypass, or quality retry/rescue.
- **First actual HTTP 503 or 429 stops the entire Fresh run**, without retry or next-model fallback; the failed attempt is counted. Other recoverable provider failures may fall back *only* inside the total and Deep Dive send limits. A timeout without observed provider response is still conservatively counted toward the Fresh attempt allowance even if the persistent RPD ledger later reconciles.
- Do not start a provider run until its daily quota is known sufficient. The independent zero-Gemini source preflight (Stage 1, optionally Stage 2 separately) is the readiness check; `FRESH_PRE_SCREEN_ONLY` does **not** predict a Gate PASS.
- A shortage, pre-Deep-Dive evidence refusal, 429, 503, or budget abort **before Gates** remains **UNMEASURED**. Once an untouched candidate reaches all unchanged Gates, a Gate failure is a measured FAIL and closes the series; never retry the same article as a Fresh holdout.

## Operational safeguards

Only an explicit, manual source-specific `local_skills_canary_validation` run with `fresh_campaign_confirm=LOCKED_FRESH_0_OF_4` opts into this campaign. The guard is installed after the validated runtime overlays, before any canary source/Notion calls. A source-specific canary without the lock is refused; ordinary Daily and generic canary remain unchanged. Lock audit contains aggregate attempt counts, not candidate content or secrets. The authoritative Canary audit must independently show `all_gate_pass=true`, Fact/Editorial/Publication PASS, Human Appeal ACCEPTABLE, non-reused provider article, no persistence/publication before crediting 1/4; a process success alone never certifies a PASS.

**No live source preflight, Daily, or Fresh is authorized by this PR.** Do not dispatch any test with real provider/source credentials during implementation. First merge only after zero-provider CI and verify exact main fingerprint; inspect Stage-1 source preflight results separately and await actual untouched availability before any 0/4 measurement.
