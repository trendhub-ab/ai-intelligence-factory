# V2-005B Source Portfolio Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only OfficialVendor and GitHub acquisition to V2 shadow so representative four-source Live Proof can run before V2-006.

**Architecture:** Reuse the existing bounded live-shadow acquisition contract and V2-005A selection layer. Add separate read-only source adapters for OfficialVendor and GitHub, preserve HN/arXiv behavior, and keep the existing single-rank Evidence budget and Production isolation.

**Tech Stack:** Python 3.11, pytest, requests, existing V2 shadow modules.

**Spec:** `docs/superpowers/specs/2026-10-15-v2-005b-source-portfolio-expansion-design.md`

## Global Constraints

- V2-005B starts only after V2-005A is verified.
- V1 remains Production authority.
- OfficialVendor + GitHub + Hacker News + ArXiv are the target V2 shadow source portfolio.
- X remains discovery-only; Product Hunt remains retired.
- Added Production mutations = `0`.
- Rank #1 remains the only Evidence candidate.
- Provider Evidence request budget remains at most `1`; retry = `0`; model fallback = `0`; rank fallback = `0`.
- No Notion, note, Ready, delivery, subscriber, economic, publication, or Production mutation.

## Review Focus

1. OfficialVendor adapter must retrieve only approved vendor-primary pages/endpoints and fail closed on malformed payloads.
2. GitHub adapter must remain read-only and bounded; repository activity must not become an unbounded crawl.
3. Failure of one source must not consume another source's budget or abort the whole shadow run.
4. Four-source total candidate budget must remain explicit and deterministic.
5. Source identity must not itself add Selection Value; V2-005A scoring remains content-based.

---

### Task 1: Design and test bounded OfficialVendor acquisition

Write RED tests first for a read-only bounded adapter, then implement the smallest adapter that maps vendor-primary records into the existing normalized candidate contract. No Production persistence or model calls.

### Task 2: Design and test bounded GitHub acquisition

Write RED tests first for read-only bounded GitHub acquisition, then implement the smallest adapter that maps repository/release activity into the existing normalized candidate contract. No mutation-capable GitHub surface.

### Task 3: Integrate four-source bounded acquisition

Write RED tests proving OfficialVendor + GitHub + Hacker News + ArXiv share an explicit total candidate budget, isolate source failures, and feed the same V2 selection/Evidence path without changing rank #1 / one-request constraints.

### Task 4: Full verification and four-source Live Proof readiness

Run focused tests, full pytest, repository guards, inspect the final diff for Production isolation, and open a Draft PR only. Stop before merge; separate `MERGE GO` is required. After merge, run 3–5 independent four-source Live Proofs before any V2-006 promotion decision.
