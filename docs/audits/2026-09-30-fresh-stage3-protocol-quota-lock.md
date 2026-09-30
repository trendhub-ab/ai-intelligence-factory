# Stage 3 — Fresh protocol fingerprint and API-budget lock

Registered on 2026-09-30 after Stage 1 (#658) and Stage 2 (#659).

## What is now enforced

Before the existing `local_skills_canary_validation` entrypoint can send any model request, `.github/workflows/daily-one-shot.yml` runs the offline `fresh_protocol_quota_lock.py` guard. It validates exact Git blob fingerprints for the Local Skills Writer, Canonicalizer, Evidence Boundary, compiler/A+ layer, source/candidate identity logic, selection code, production runtime layers, publication/Reader Value gates, the canary itself, the Production entrypoint, and the canary-capable workflow.

It also fails closed if the four registered sources or these configured bounds drift:

- each source acquisition presentation cap: 50
- shared screening ceiling: 200
- screening batch size: 25
- global calibration batch size: 50
- workflow Deep Dive request budget: 12
- canary article-analysis Deep Dive sends: **at most 1**
- canary quality retries: **0**
- deterministic publication rescue after measurement: **disabled**

For one exact source, the pre-model structure can present at most 50 candidates, so the registered **logical** model work bound is up to 2 screening batches + 1 calibration batch + 1 Deep Dive send.

## Critical quota limitation

This lock deliberately does **not** say that only four HTTP/provider attempts will occur. Model fallbacks, transient errors, and transport retry/accounting can consume more attempts than the logical batch count. There is no trustworthy zero-cost API endpoint in this implementation that proves the current Gemini RPM/RPD remainder. Therefore the lock returns:

- `actual_provider_rpm_rpd_remaining = NOT_MEASURED`
- `safe_to_start_without_quota_review = false`

The operational rule remains: **do not start Fresh while Gemini rate limits are tight**. A 429/503 before a Gate measurement is UNMEASURED, never a quality FAIL or PASS.

## Relation to Stage 2

The optional `source-supply-gh-3-cohorts-v1` experiment is intentionally excluded from this lock. If that experimental acquisition rule is ever adopted, the current lock must fail/retire and an independent new four-source Fresh campaign starts at **0/4** with a new fingerprint. The historical source-stratified result remains 1/4 (HackerNews PASS; GitHub, ArXiv, OfficialVendor UNMEASURED).

No Daily or Fresh run was launched to implement this lock.
