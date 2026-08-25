# Free Article Delivery Reliability Release Validation

Date: 2026-08-22 (JST)
Scope: Revenue Product Phase 2 + free note acquisition pipeline

## Executive Decision

The prior Phase 2 release was safe but not sufficient as a business release because repeated production runs could finish with `Ready=0`. This release does **not** weaken evidence/fact safety. It changes the system so that publishability is optimized as a first-class acquisition objective while paid Decision Intelligence remains decoupled.

Release status for offline/code validation: **PASS**.
Live business acceptance remains **PENDING one normal Daily production run**, because live Gemini/provider availability and fresh source quality cannot be proven offline.

## Changes that directly improve article yield

1. **Article/Product Review prompt separation**
   - Free article Deep Dive asks for only 8 minimal management fields.
   - Adoption Score / Adoption Status / Evidence Confidence / Production Readiness / Main Risk / Best For / Avoid For are generated only by Product Review.
   - Parser remains backward compatible with old Deep Dive outputs.

2. **Publication-safe Fact Gate scope**
   - Fact Gate requires publication-critical management fields only: Decision Reason, Action, Source Summary.
   - Alternative Comparison, Migration Cost, Future Scenario and similar product-completeness fields are no longer mandatory article facts.
   - Fact safety itself remains fail-closed.

3. **False-positive correction**
   - Negation is checked in the same Japanese sentence rather than a fixed 40-character window.
   - Example now handled correctly: `今すぐ…リアーキテクチャすることは推奨しません`.
   - `2026年8月` calendar expressions are not mistaken for unsupported duration claims.

4. **0-API deterministic publication rescue**
   - Before spending a Gemini quality-retry request, narrowly diagnosed local defects can be removed subtractively.
   - Supported rescue: unsupported hype, unsupported numeric sentence, unsupported named-fact sentence, fabricated personal experience.
   - Generic unsupported claims, evidence gaps, unsafe Action, title numeric/named-fact defects remain fail-closed.
   - Rescue re-runs Fact / Publication / Human checks before Ready.

5. **Publication Reliability slot**
   - One visible Deep Dive slot may be promoted by a 0-API metadata-only publishability proxy.
   - Promotion requires Decision Score >= 65 and a meaningful publishability advantage.
   - Other slots remain optimized for business/commercial value.

6. **Acquisition-first model scheduling**
   - Order: Fresh article candidates -> Deferred (never attempted) -> Pending Retry (previous failures) -> Product Review.
   - Paid Product Review cannot mark the Flash model pool unavailable before today’s free acquisition attempt.
   - Product Review retains its own small request cap and still shares the global/persistent Gemini safety caps.

## Run 97 real-manuscript replay

The two actual Run 97 final failed manuscripts were frozen as regression fixtures.

- Software Form article:
  - old final blockers included unsupported `唯一`, score narrative mismatch, weak opening hook.
  - sentence-scope negation removes the false `score_narrative_mismatch`.
  - deterministic rescue removes the isolated unsupported hype without adding facts.

- Learning When to Think article:
  - old final blockers included unsupported `8月`, unsupported `Llama`, `デファクトスタンダード`, repetitive intro, score narrative mismatch.
  - current Gate logic no longer treats calendar `2026年8月` as a duration claim, and no longer treats the negated phrase `デファクトスタンダードというわけではありません` as positive hype.
  - the remaining unsupported named fact (`Llama`) is locally removable without inventing replacement facts.
  - frozen old reason codes are also replayed to prove backward-safe subtractive rescue, but those obsolete false-positive reason codes should not be generated in a new run.

Replay result: **2/2 known Run 97 final blocker sets reach the rescue-ready policy** under the recorded final-gate conditions.

This is a regression proof of the logic change, **not** a claim that a future live Daily must always publish. Live source evidence and provider availability still govern publication.

## Regression results

- Free Article Delivery dedicated tests: 19/19 PASS
- Full unittest suite: 364/364 PASS
- Full pytest suite: 364/364 PASS
- Synthetic Regression Full: 500/500 PASS
- Synthetic critical failures: 0
- Production write isolation: true
- Python compile: PASS
- Workflow YAML: 5/5 PASS
- `migrate_decision_intelligence.py`: byte-identical to the formal Phase 2 base
- `requirements.txt`: byte-identical to the formal Phase 2 base

## Business acceptance rule after deployment

The next normal Daily is a required live acceptance run.

A Daily with `Ready=0` is allowed only when the trace supports a real external/safety reason such as:
- primary evidence insufficient,
- all viable Deep Dive models provider-unavailable,
- actual daily/model quota exhaustion,
- all generated drafts still contain non-repairable fact defects.

If Stock and evidence are healthy, at least one generation succeeds, but `Ready=0` remains, the release is treated as **business-degraded** and the gate/retry artifact must be reviewed. We do not declare the article acquisition engine complete merely because unit/synthetic tests pass.

## What was intentionally NOT done

- Fact/Evidence safety was not globally loosened.
- A forced “publish one article no matter what” fallback was not added.
- Gemini paid quota was not enabled.
- Legacy migration logic was not changed.
- Subscriber/Monthly destination flags remain independently controlled.
