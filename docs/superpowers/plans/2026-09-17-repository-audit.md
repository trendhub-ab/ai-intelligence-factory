# Repository Contract Audit Implementation Plan

> **For agentic workers:** Use the Superpowers debugging/TDD cycle task by task. This session executes the already-authorized audit and fixes inline.

**Goal:** Repair reproduced cross-module inconsistencies without weakening Production gates, quotas, or publication safety.

**Architecture:** Keep the canonical Production wrapper order and generation/persistence implementation. Correct only dispatch admission, validation outcome interpretation, canonical discovery-source contracts, and fan-out audit validation.

**Tech Stack:** Python, pytest/unittest, GitHub Actions shell, Notion public API contracts.

**Spec:** User audit request and `AI_Intelligence_Factory_最終仕様書.md`.

## Global Constraints

- Gemini/Google/Groq and Apify calls: zero during this audit.
- Scheduled Daily: PAUSED. No note publication, Notion mutation, or historical recovery execution.
- Fact/Evidence/Reader/Publication criteria, persistent counters, per-model quotas, and total Deep Dive budget: unchanged.
- X remains discovery-only; raw posts never become Evidence.
- Do not remove Run layers or compatibility surfaces without behavioral proof.

## Evidence and Baseline

- Remote main: `c6bb452a9ea308b24564a090fb5821e973a1daad`; remote tree: `160ed9250646740d8ddc046f90d198557fe786d0`.
- All 1,029 tracked blobs matched GitHub Git blob SHA. Work uses a separate local checkout/branch.
- Baseline: 2,663 tests passed; nine structural guards passed.
- Added reproductions: `tests/test_repository_audit_contracts.py`; before fixes: 20 FAIL, 2 PASS, no collection errors.

## Task 1: Dispatch safety and Pending Retry parity

Files: `production_pipeline.py`, `run280_publication_dependency_guard.py`, audit tests.

- [x] Reproduce unknown/malformed mode falling into normal Production, and direct Pending mode calling an API that does not accept `pending_only`.
- [x] Validate explicit modes and malformed event input before setup; preserve normal local/synthetic and valid other-workflow events without mode input.
- [x] Delegate Pending mode to existing bounded `pending_retry_validation.main()` before importing/initializing Production.
- [x] Run mode tests and existing runtime/parity/dependency tests.

## Task 2: Explicit validation outcomes

Files: `article_revalidation.py`, `tests/test_run277_article_revalidation.py`, audit tests.

- [x] Reproduce legacy string/dict/unknown-status results being accepted or incorrectly classified.
- [x] Use the established Pending Retry nonpersistent classifier; count unknown results separately as `unverified`, never `accepted`.
- [x] Keep `persist_results=False` and existing request ceilings.
- [x] Run focused article-validation tests.

## Task 3: X public discovery contract

Files: `publication_source_contract.py`, `tests/test_run281_publication_causality_source_contract.py`, audit tests.

- [x] Reproduce X-origin candidate exclusion at `note_ready_sync._source_state`.
- [x] Add the already-integrated optional X discovery source to the canonical public allowlist/label/rights note, explicitly excluding raw posts from Evidence.
- [x] Preserve current-policy manuscript hash validation, unsupported/retired source rejection, and four-source allocation.
- [x] Run X, source, Ready sync, and private-draft safety tests.

## Task 4: Current Notion schema enum authority

Files: `content_db_contract_guard.py`, audit tests.

- [x] Reproduce current-only schema failing for absent retired ProductHunt and schemas lacking OfficialVendor/X passing.
- [x] Derive required source enums from the canonical source contract; keep other schema safety checks.
- [x] Verify current schemas pass and missing active sources fail.

## Task 5: Fail-closed Rescue fan-out

Files: `.github/workflows/daily-one-shot.yml`, audit tests.

- [x] Run the actual workflow shell with local fake `gh`: missing/corrupt audit is silently success, boolean `true` dispatches.
- [x] Distinguish invalid audit (failure), valid integer Ready 0 (no-op), and positive Ready (existing dispatch).
- [x] Preserve GH_PAT-only dispatch and exact downstream workflow.
- [x] Run the actual shell for all invalid/zero/positive fixtures.

## Task 6: Cross DB contract and initialized Rescue accounting

- [x] Reproduce retired Source requirements in Technology / Subscriber / Member schemas.
- [x] Share active Publication sources plus the existing Unknown compatibility value.
- [x] Reproduce real main erasing Rescue audit, counter and Ready totals.
- [x] Move Rescue to a hook after run resets and carry generated count / candidate rank into Fresh and Backlog.
- [x] Keep TOP_N and the cumulative 12-request ceiling; independent review proves Rescue 1 + Fresh 2 = Ready 3.

## Task 7: Raw X redirect and persisted Evidence safety

- [x] Reproduce X adapter/redirect material entering primary context and authoritative Evidence.
- [x] Reject X / Twitter / t.co at HTTP and Authority boundaries while retaining normal primary retrieval.
- [x] Reproduce and fix DNS terminal-dot bypass, plus preserve malformed URL empty fetch handling.
- [x] Add local fake-response tests; no external acquisition or generation.

## Final verification

- [x] Full deterministic pytest (2,702 PASS), compileall, 14 structural guards, assembled Production synthetic smoke (30/30), and regression self-test.
- [x] Independent review of the concrete diff; fix any reproduced review findings.
- [x] Update canonical spec and audit report with severity, evidence, remaining risks, and validation limits.
- [x] Submit fixes on reviewable PR #380 and confirm remote zero-provider CI: 2,702 PASS on Python 3.11.16, smoke 30/30, six successful CI checks on code commit 74febf786e913594cf9b0cb7b25e642a395a7ed0. Live Notion jobs skipped. Do not claim real generation or note E2E success.
