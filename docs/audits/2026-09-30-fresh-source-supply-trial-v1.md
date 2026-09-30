# Stage 2 preregistration — GitHub source-supply feasibility trial v1

**Registered 2026-09-30, before any live experimental query.**

Protocol: `source-supply-gh-3-cohorts-v1`. This is an **optional separate discovery feasibility experiment** and is NOT the prior source-stratified v4.3.9 Fresh campaign. The completed prior campaign remains HN measured PASS and GitHub/ArXiv/OfficialVendor UNMEASURED (1/4). Run #36678612521's 33 GitHub duplicate exclusions do not separate existing Notion and intra-run reasons; PR #656 added future counters.

## Rationale, exact queries and limits

Existing GitHub source discovery takes at most 50 repositories from one narrow intersection: `topic:ai topic:machine-learning stars:>100 pushed:>{UTC today - 30 days}`. In the measured run, 50 raw, 33 legally safe, 33 duplicate excluded, 0 fresh.

Propose EXACTLY three independent 30-day GitHub GraphQL repository cohorts, in the following frozen order:
1. Baseline `topic:ai topic:machine-learning stars:>100 pushed:>{date}`
2. Generative AI `topic:generative-ai stars:>100 pushed:>{date}`
3. LLM `topic:large-language-model stars:>100 pushed:>{date}`

Each GraphQL call returns at most 50 candidates, using identical original GitHub metadata fields. Fail closed if **any** query fails. Unique repository identities are interleaved across the three lists before a **single 50-item GitHub presented cap**. Normal current legal check, authoritative Notion dedupe, already-observed exclusions, existing 200-item shared screening ceiling and all current article-quality thresholds are retained. Three bounded GitHub queries consume **two additional GitHub source API calls relative to baseline, zero Gemini calls**. This trial is run only when the user separately selects `gh_3cohort_trial` and enters `ALLOW_3_GITHUB_READS` in the manual source-preflight workflow. Do not launch while source API limits are tight.

## Other two unavailable sources

**ArXiv:** 13 fresh in prior source run; none met current Deep Dive threshold. Source discovery was not the demonstrated bottleneck. Wait for new articles and evaluate on unchanged future screening; do not lower decision or Gate thresholds to fabricate a passing candidate.

**OfficialVendor:** two fresh in prior source run, neither qualified. Current vendor registry is the trusted allowlist. Do not add unvetted external brands, scrape third-party opinion as vendor primary Evidence, lower the threshold, or silently reuse already observed articles. A future registry expansion needs independent provenance/legal review and a separate preregistration before live testing.

**HackerNews:** one valid measured prior PASS and several distinct historical mixed Fresh PASS observations. Those candidates are quarantined; previous success does not substitute for a new untouched holdout.

## Decision rule

This trial's output is labelled `EXPERIMENTAL_GITHUB_SOURCE_SUPPLY_NOT_PRODUCTION`, counts only candidates and never assigns score, Gate result or publication readiness. Compare per-query raw and uniquely presented aggregates and the four-source dedupe counts to an independently observed baseline preflight when quotas allow. If the trial yields no fresh legally safe GitHub candidates or requires changing quality policy, stop. If it improves candidate supply, register **a new four-source 0/4 Fresh experiment** with its own source-acquisition hash and frozen model-call budget. No changes to the validated Production/Daily source path or older Fresh certification occur in this PR.
