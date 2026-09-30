# Fresh source diagnostics: zero-provider audit (2026-09-30)

## Scope and provenance

This is an **offline test-hardening audit**, not a new Fresh run. Baseline: main `bbbfdcdc230da436b408acfa7af984bc9a95d84a` (PR #656). No LLM provider calls, external source refresh, Notion reads/writes, note publishing, changes to Writer, Canonicalizer, Evidence Boundary, Gate policy, acquisition breadth, selection policy, thresholds or candidate quarantine.

## Observed historical evidence (before PR #656)

Run [36678612521](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/36678612521), source GitHub, logged: 50 collected; 33 legal-safe; 33 duplicate-excluded; 0 Fresh; no screening, article-generation send or Gate measurement. The split between **existing Notion** and **same-run** duplicates was not measured in that run. Never infer that all 33 were Notion duplicates simply from this aggregate. The aggregate is the union: a candidate may have both duplicate reasons.

Prior source-stratified campaign (#654): HackerNews measured PASS; GitHub, ArXiv, OfficialVendor UNMEASURED. The separate four-pass mixed-source v4.3.9 certification (#652) does not prove cross-source 4/4.

## Frozen-protocol review

- A source-restricted canary still **fetches all four discovery sources** before common round-robin, legal checks, global dedupe and source restriction. Source restriction is not an external API saving switch. Do not trigger a canary while quotas are constrained.
- Global within-run dedupe occurs before source restriction. If HN and GitHub candidates share an identity and HN appears first, the later GitHub candidate can be excluded even if neither is in Notion. Existing diagnostics classify this as an intra-run duplicate; absent further measurement it must not be called existing-Notion saturation.
- No candidates after source restriction must stop **before** Screening/Calibration/Deep Dive, preserving provider budget. An invalid source must fail before runtime initialization. New mocked tests cover these boundaries.
- PR #656's existing-Notion and intra-run reason counters can overlap. The aggregate duplicate-excluded count must not be computed by adding them without correcting overlap.

## Next action after quota recovery

Run the exact GitHub source canary once under the unchanged, preregistered protocol to gather #656's fresh reason split. If a source remains unable to produce an untouched eligible candidate, propose a **new**, independently registered acquisition/selection experiment instead of changing protocol mid-claim. Do not relabel unmeasured as PASS or claim a new 4/4 based on these offline tests.
