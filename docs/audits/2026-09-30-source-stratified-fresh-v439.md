# Source-stratified Fresh validation audit — 2026-09-30

## Pre-registered protocol
Use unchanged v4.3.9-integrated Local Skills Writer, Canonicalizer, stage10-v4 Evidence Boundary, and all existing Evidence/Fact/Editorial/Publication/Human Appeal Gates. Run one untouched, source-specific Fresh holdout per GitHub, HackerNews, ArXiv and OfficialVendor. For each source, reuse Production collection limits (50 each), legal checks, Notion dedupe, Screening, Calibration, source preflight and candidate threshold. No source substitution, Gate relaxation, quality retry, rescue, note publication, or Notion article persistence. Pre-Deep-Dive absence or 503 without Gate measurement is **unmeasured**, never a quality PASS or FAIL.

All four source-restricted runs executed from main `4ebb45b54672d3fee71bcb9a23df30b3dd52b6af` after infrastructure PR #653's CI passed. Local Skills Writer and Canonicalizer hashes were unchanged: `884c550125ff563b2d8bcf20132f3373d332f28d` and `93a62ef2311d43dc1cb84fa5affe9d798a133021`.

## Actual results

| Required discovery route | GitHub Actions Run | Fresh after Production dedupe | Actual outcome | Quality measurement |
| --- | --- | ---: | --- | --- |
| GitHub | 36676634120 | 0 | No candidate survived existing Notion dedupe | **UNMEASURED** |
| HackerNews | 36676874086 | 19 | `Inspect: An open-source framework for large language model evaluations`; primary `https://inspect.aisi.org.uk/`. Fact/Editorial/Publication PASS, Human Appeal ACCEPTABLE, `all_gate_pass=true`, provider article reused=false | **PASS (1)** |
| ArXiv | 36677175998 | 13 | All 13 screened; 0 candidates qualified for unchanged Production Deep Dive threshold | **UNMEASURED** |
| OfficialVendor | 36677369285 | 2 | Both screened; 0 candidates qualified for unchanged Production Deep Dive threshold | **UNMEASURED** |

Provider costs observed: GitHub had zero model sends; HackerNews 4 Gemini attempts (3 successful, 1 failed); ArXiv 2 successful Screening/Calibration attempts; OfficialVendor 1 successful Screening attempt. No article-level provider send or Local Skills Gate measurement happened for GitHub/ArXiv/OfficialVendor.

## Decision

**The source-stratified Fresh 4/4 claim is NOT satisfied.** The honest result is 1 source measured and PASS, 3 sources unmeasured due to candidate availability and current Production selection conditions, not three Gate quality failures. The preceding v4.3.9 mixed-source Fresh 4/4 remains factually valid for four distinct HackerNews-discovered articles, but proves no cross-source coverage.

This audit must not relabel the three unmeasured outcomes as success, nor lower publication quality thresholds to manufacture eligible articles. The observed HackerNews article is now excluded from future Fresh holdouts by both its title and primary URL marker.

## Next measured prerequisite

Diagnose source-specific candidate attrition and freshness at zero provider cost first. In particular, GitHub GraphQL currently samples at most 50 AI/ML repositories from one 30-day query, of which none survived Production dedupe; ArXiv had 13 fresh items but none met the existing Deep Dive selection threshold; OfficialVendor had only 2 fresh items and neither qualified. Any changed acquisition breadth or stratified selection protocol constitutes a **new, explicitly preregistered experiment**, and may not be combined retroactively with this campaign's results.

After viable untouched candidates exist for all four discovery sources under defensible unchanged quality checks, restart an independent four-source Fresh 0/4 series. Production promotion is a separate persistence / end-to-end validation stage.
