# V2 Source Acquisition Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give all four V2 acquisition families one bounded, shared transient-failure policy and safe diagnostics without changing Production authority or healthy-path request counts.

**Architecture:** Add one provider-free GET reliability helper that owns transport/HTTP classification, at-most-one retry, and safe per-logical-read diagnostics. Existing source readers keep their allowlists, parsing, normalization, and natural redundancy; they call the helper for each individual GET. `v2_four_source_live.py` aggregates safe diagnostics into the Shadow report while source failure isolation remains unchanged.

**Tech Stack:** Python 3.11, `requests`, pytest, existing V2 shadow modules.

**Spec:** `docs/superpowers/specs/2026-10-17-v2-source-acquisition-reliability-gold-benchmark-design.md`

## Global Constraints

- V1 Production authority, article generation, Ready, Notion, note, eyecatch, and publication flows must not change.
- Retry only timeout, connection failure, HTTP 429, and HTTP 5xx.
- Maximum one retry per logical HTTP read: first attempt + at most one retry.
- HTTP 4xx except 429 and invalid JSON/XML/HTML/payload/redirect/allowlist failures are not retried.
- Healthy path remains one HTTP attempt per logical read.
- One source family failure must not stop remaining source families.
- Never persist raw bodies, credential-bearing headers, tokens, API keys, or transport exception messages.
- No extra Gemini calls and no Production writes.

## Review Focus

- A fake response whose `status_code` is absent but `raise_for_status()` fails must become safe `request_failure`, never leak exception text; Task 1 pins this.
- A retryable first failure followed by a permanent second failure must stop after attempt 2 and report both first and final safe categories; Task 1 pins this.
- Multi-read families must not retry the whole family loop after one logical read already exhausted its two attempts; Tasks 2 and 3 pin this.
- HN item-level failure must remain isolated even after retry support; Task 3 pins this.
- Top-level telemetry must not misrepresent total HTTP attempts as the existing provider call count; Task 4 pins this.

---

### Task 1: Shared bounded GET reliability helper

**Files:**
- Create: `v2_acquisition_reliability.py`
- Create: `tests/test_v2_acquisition_reliability.py`

**Interfaces:**
- Produces: `AcquisitionRequestError(category: str, diagnostics: AcquisitionDiagnostics)`.
- Produces: immutable `AcquisitionDiagnostics(attempt_count: int, retry_used: bool, first_failure_category: str | None, final_failure_category: str | None)` with `as_dict() -> dict[str, object]`.
- Produces: `bounded_get(*, http_get: Callable[..., Any], url: str, timeout: float, request_kwargs: Mapping[str, Any] | None = None, sleep_fn: Callable[[float], None] = time.sleep, retry_delay_seconds: float = 0.25) -> tuple[Any, AcquisitionDiagnostics]`.

- [ ] **Step 1: Write RED tests for category classification and retry boundaries**

Add tests asserting:

```python
assert timeout_then_success.diagnostics.attempt_count == 2
assert timeout_then_success.diagnostics.retry_used is True
assert timeout_then_success.diagnostics.first_failure_category == "timeout"
assert response_400.calls == 1
assert response_429_then_success.calls == 2
assert response_503_then_success.calls == 2
assert connection_then_connection.calls == 2
```

Also assert invalid/unknown exceptions are safe `request_failure`, `sleep_fn` is called exactly once only when retrying, and secret exception/body text never appears in raised error or diagnostics.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_v2_acquisition_reliability.py`

Expected: FAIL because `v2_acquisition_reliability` does not exist.

- [ ] **Step 3: Implement minimal helper**

Implement exact taxonomy used by the spec: `timeout`, `connection`, `http_429`, `http_5xx`, `http_4xx`, `request_failure`. Inspect `status_code` before calling `raise_for_status()` so 429/5xx classification is deterministic. Retry only the four transient categories and stop after attempt 2.

- [ ] **Step 4: Run focused tests GREEN**

Run: `python -m pytest -q tests/test_v2_acquisition_reliability.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add v2_acquisition_reliability.py tests/test_v2_acquisition_reliability.py
git commit -m "feat: add bounded V2 acquisition retry contract"
```

### Task 2: OfficialVendor and GitHub integration

**Files:**
- Modify: `v2_official_vendor_live.py`
- Modify: `v2_github_live.py`
- Modify: `tests/test_v2_official_vendor_live.py`
- Modify: `tests/test_v2_github_live.py`

**Interfaces:**
- Consumes: Task 1 `bounded_get` and `AcquisitionDiagnostics`.
- Produces: existing public reader return shapes unchanged.
- Produces: optional keyword-only `diagnostic_sink: Callable[[Mapping[str, Any]], None] | None = None` on each logical-read function and family function; omission preserves current callers.

- [ ] **Step 1: Write RED retry tests in existing source suites**

For each family prove 503→200 recovers on the same logical URL with exactly two GETs; 400 uses one GET; redirect-host rejection is never retried; invalid HTML/JSON is never retried. Preserve existing allowlist/token secrecy assertions.

- [ ] **Step 2: Write RED natural-redundancy tests**

OfficialVendor: one vendor exhausting two attempts must not restart the three-vendor loop and remaining vendors still execute once each on healthy path.

GitHub: one repository exhausting two attempts must not restart the three-repository loop and remaining repositories still execute once each on healthy path.

- [ ] **Step 3: Run RED**

Run: `python -m pytest -q tests/test_v2_official_vendor_live.py tests/test_v2_github_live.py`

Expected: new retry assertions FAIL while existing tests remain PASS.

- [ ] **Step 4: Integrate the shared helper minimally**

Replace only request/status handling. Keep URL/host validation, HTML/JSON parsing, candidate normalization, source order, limits, and family failure rules in their current modules. Map non-HTTP parsing failures to existing source-specific categories.

- [ ] **Step 5: Run focused tests GREEN**

Run: `python -m pytest -q tests/test_v2_acquisition_reliability.py tests/test_v2_official_vendor_live.py tests/test_v2_github_live.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add v2_official_vendor_live.py v2_github_live.py tests/test_v2_official_vendor_live.py tests/test_v2_github_live.py
git commit -m "feat: apply bounded retry to V2 vendor and GitHub reads"
```

### Task 3: HackerNews and ArXiv integration

**Files:**
- Modify: `v2_live_shadow_acquisition.py`
- Modify: `tests/test_v2_live_shadow_acquisition.py`
- Modify: `tests/test_v2_live_shadow_acquisition_budget.py` only if injected diagnostics require fixture adaptation.

**Interfaces:**
- Consumes: Task 1 `bounded_get`.
- Produces: `fetch_hacker_news_candidates(..., diagnostic_sink=None)` and `fetch_arxiv_candidates(..., diagnostic_sink=None)` while preserving current return values and limits.

- [ ] **Step 1: Write RED source-level retry tests**

HN topstories: timeout→success and 429→success use exactly two attempts; HTTP 400 uses one.

ArXiv: timeout→success, 503→success use exactly two attempts; 400 and malformed XML use one request only.

- [ ] **Step 2: Write RED HN item isolation test**

One item timeout twice is skipped after two attempts; the next item is still fetched and survives. Assert the topstories request is not repeated because an item failed.

- [ ] **Step 3: Run RED**

Run: `python -m pytest -q tests/test_v2_live_shadow_acquisition.py tests/test_v2_live_shadow_acquisition_budget.py`

Expected: new recovery tests FAIL.

- [ ] **Step 4: Integrate shared helper**

Use one bounded logical read per HN topstories URL, each HN item URL, and the single ArXiv query. Preserve `ARXIV_SEARCH_QUERY`, result ordering, existing XML parser, HN filtering, and all acquisition caps.

- [ ] **Step 5: Run focused tests GREEN**

Run: `python -m pytest -q tests/test_v2_acquisition_reliability.py tests/test_v2_live_shadow_acquisition.py tests/test_v2_live_shadow_acquisition_budget.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add v2_live_shadow_acquisition.py tests/test_v2_live_shadow_acquisition.py tests/test_v2_live_shadow_acquisition_budget.py
git commit -m "feat: apply bounded retry to V2 HN and ArXiv reads"
```

### Task 4: Aggregate safe source diagnostics into V2 Shadow artifact

**Files:**
- Modify: `v2_four_source_live.py`
- Modify: `v2_shadow_selection.py`
- Modify: `tests/test_v2_four_source_live.py`
- Modify: `tests/test_v2_005_live_proof.py`

**Interfaces:**
- Consumes: source `diagnostic_sink` events from Tasks 2–3.
- Produces: report key `source_acquisition_diagnostics` mapping `OfficialVendor`, `GitHub`, `HackerNews`, `ArXiv` to safe aggregates: `logical_read_count`, `http_attempt_count`, `retry_used`, `first_failure_category`, `final_failure_category`.
- Keeps `actual_calls["provider"] == 4`; HTTP-attempt telemetry is separate and must not alter model/provider logical-call semantics.

- [ ] **Step 1: Write RED artifact tests**

Prove healthy run shows no retry and expected HTTP attempt totals; transient recovery records `retry_used=True` and first failure; exhausted failure records final category; no secret body/header/token text is serialized.

- [ ] **Step 2: Pin provider exception category preservation**

Update `run_shadow_selection` provider-boundary reporting to prefer a safe `.category` attribute when present, otherwise retain `type(exc).__name__`. Assert secret messages are never serialized.

- [ ] **Step 3: Run RED**

Run: `python -m pytest -q tests/test_v2_four_source_live.py tests/test_v2_005_live_proof.py`

Expected: telemetry assertions FAIL.

- [ ] **Step 4: Implement aggregation**

Collect only structured safe events. Do not include URL, body, headers, exception strings, or request parameters in artifact telemetry.

- [ ] **Step 5: Run V2 safety suite**

Run:
`python -m pytest -q tests/test_v2_acquisition_reliability.py tests/test_v2_official_vendor_live.py tests/test_v2_github_live.py tests/test_v2_live_shadow_acquisition.py tests/test_v2_live_shadow_acquisition_budget.py tests/test_v2_four_source_live.py tests/test_v2_005_live_proof.py tests/test_v2_variable_gemini_fallback.py tests/test_v2_shadow_deep_dive_workflow.py`

Expected: PASS and existing Gemini budgets unchanged.

- [ ] **Step 6: Commit**

```bash
git add v2_four_source_live.py v2_shadow_selection.py tests/test_v2_four_source_live.py tests/test_v2_005_live_proof.py
git commit -m "feat: expose safe V2 source acquisition diagnostics"
```

### Task 5: Workflow safety-suite inclusion and repository verification

**Files:**
- Modify: `.github/workflows/v2-shadow-deep-dive.yml`
- Modify: `tests/test_v2_shadow_deep_dive_workflow.py`
- Modify: `AI_Intelligence_Factory_最終仕様書.md` only if the Production fingerprint guard requires synchronization because a monitored Production surface changed.

**Interfaces:**
- Adds provider-free `tests/test_v2_acquisition_reliability.py` to the pre-live workflow safety suite.
- Does not add secrets, permissions, schedules, or model calls.

- [ ] **Step 1: Write RED workflow assertion**

Require `tests/test_v2_acquisition_reliability.py` in the reviewed test list and preserve the existing workflow name/model-request ceiling.

- [ ] **Step 2: Update workflow test list only**

Do not change dispatch, permissions, concurrency, secrets, live command, or artifact retention.

- [ ] **Step 3: Run focused workflow tests**

Run: `python -m pytest -q tests/test_v2_shadow_deep_dive_workflow.py`

Expected: PASS.

- [ ] **Step 4: Run full verification on exact head**

Run focused V2 suite, then `python -m pytest -q`, Repository-wide Falsification Guard, P0-B Offline Verification, Notion Access Policy Guard, Workflow Reference Guard, and Synthetic Production smoke. Confirm `production_write_isolation=true`.

- [ ] **Step 5: Commit any guard-required canonical metadata sync separately**

Never weaken a guard to make it pass.

- [ ] **Step 6: Stop at merge-ready**

Open/update Draft PR with RED/GREEN evidence and changed-file inventory. Do not provider-back a failure injection and do not merge without explicit MERGE GO.
