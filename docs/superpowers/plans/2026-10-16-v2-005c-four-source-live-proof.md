# V2-005C Four-Source Live Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the merged V2-005B four-source portfolio to the measured V2-005 Live Proof path with bounded GET-only OfficialVendor/GitHub readers, preserving one Gemini Evidence request maximum and zero Production mutation authority.

**Architecture:** Add two focused read-only live readers in front of the existing OfficialVendor/GitHub normalizers, then compose those with the existing Hacker News/arXiv readers at one four-source acquisition boundary. Route `v2_005_live_proof.py` through the existing `run_four_source_shadow()` selector/Evidence path, keep the existing ChatOps workflow/manual confirmation contract, and preserve the existing V2-005 artifact/evidence-pack contract.

**Tech Stack:** Python 3.11.16, `requests`, stdlib HTML parsing utilities, GitHub Actions, pytest 8.4.2, existing V2 shadow modules.

**Spec:** `docs/superpowers/specs/2026-10-16-v2-005c-four-source-live-proof-design.md`

## Global Constraints

- Base Production main is `686cf66cc8f93f379ee05f15fb4fa83a0d85a5ef`.
- V1 remains the sole Production authority.
- V2-005C is shadow-only and manual/ChatOps initiated only.
- No Notion, note, Ready, delivery-ledger, subscriber, Economic State, publication, or public-release mutation.
- OfficialVendor/GitHub acquisition is HTTP GET only.
- OfficialVendor initial allowlist is exactly OpenAI `https://openai.com/news`, Anthropic `https://www.anthropic.com/news`, Google Gemini `https://blog.google/products-and-platforms/products/gemini/`.
- GitHub initial allowlist is exactly `openai/openai-python`, `anthropics/anthropic-sdk-python`, `googleapis/python-genai`.
- OfficialVendor max index items: 5 per vendor; GitHub max releases: 5 per repository.
- OfficialVendor/GitHub timeout: 8 seconds per GET.
- GitHub Live Proof uses releases only; no tag/changelog fallback.
- Four source families remain exactly `official_vendor`, `github`, `hacker_news`, `arxiv`.
- Only rank #1 may enter Evidence.
- Gemini model remains exactly `gemini-3.6-flash`.
- Gemini Evidence requests: max 1 per run; retry 0; model fallback 0; rank fallback 0.
- No Lite model.
- Source failure is isolated; one failed source must not abort or consume remaining-source budget.
- OfficialVendor/GitHub reader failures reuse `SourceAcquisitionError(source, category)` from `v2_live_shadow_acquisition.py`; new categories are limited to `request_failure`, `http_failure`, `redirect_not_allowed`, `invalid_html`, `invalid_json`, and `invalid_payload`.
- No raw response body, prompt, token, authorization header, cookie, transport exception text, arbitrary HTML dump, or unpublished Notion/note content may enter artifacts.
- No live provider/Gemini call is required before merge.

## Review Focus

1. **Redirect escape from allowlist:** a vendor GET that lands on an unapproved hostname must fail that vendor with `redirect_not_allowed`; Task 1 owns the regression.
2. **HTML drift / deceptive anchors:** vendor pages with malformed or off-domain article links must not create candidates or trigger fallback discovery; Task 1 owns the regression.
3. **GitHub token or repository widening:** runtime inputs must not alter the three repositories or expose the token; Task 2 owns the regression.
4. **Four-source bridge accidentally bypasses `run_four_source_shadow()`:** Live Proof must use the one canonical portfolio/ranking path and one Evidence attempt; Task 3 owns the regression.
5. **Artifact/evidence-pack drift:** new source diagnostics must not break the existing V2-005 safe candidate/measurement contract or allow auto-promotion; Task 4 owns the regression.

---

### Task 1: Add bounded OfficialVendor live reader

**Files:**
- Create: `v2_official_vendor_live.py`
- Create: `tests/test_v2_official_vendor_live.py`
- Reuse: `v2_official_vendor_acquisition.py`
- Reuse: `v2_live_shadow_acquisition.py` (`SourceAcquisitionError` only)

**Interfaces:**
- Consumes: `acquire_official_vendor_candidates(...)` and existing `SourceAcquisitionError`.
- Produces:
  - `VendorSourceConfig(provider: str, collection_url: str, allowed_hostname: str, max_items: int = 5, timeout_seconds: float = 8.0)`
  - `OFFICIAL_VENDOR_SOURCES: tuple[VendorSourceConfig, ...]`
  - `fetch_official_vendor_source(*, source: VendorSourceConfig, http_get: Callable[..., Any] = requests.get) -> list[dict[str, Any]]`
  - `fetch_all_official_vendor_candidates(*, http_get: Callable[..., Any] = requests.get) -> list[dict[str, Any]]`

- [ ] **Step 1: Write RED tests for exact source configuration and bounded GET behavior**

Add tests asserting:
- `OFFICIAL_VENDOR_SOURCES` contains exactly the three spec URLs in OpenAI → Anthropic → Google order;
- every source has `max_items == 5` and `timeout_seconds == 8.0`;
- `fetch_official_vendor_source()` invokes injected `http_get` once for the configured collection URL with `timeout=8.0`;
- no callable accepts a runtime URL/hostname allowlist override.

- [ ] **Step 2: Write RED parser/fail-closed tests**

Use fixed local HTML fixtures and assert:
- only `http/https` article anchors on the exact configured hostname are accepted;
- anchor text becomes the required title; a same-card `<time datetime>` and short summary may be used when unambiguous, otherwise `published_at=None` and `description=""` are valid;
- at most 5 items are passed to the existing normalizer;
- duplicate canonical URLs collapse through the existing normalizer;
- malformed anchors and off-domain/lookalike hosts are ignored;
- a response whose final URL hostname differs from `allowed_hostname` raises `SourceAcquisitionError(..., "redirect_not_allowed")` without leaking response text;
- request/HTTP/parser failures map only to the approved safe categories;
- HTML that yields no supported candidate returns an empty list, with no crawler/search/browser fallback.

- [ ] **Step 3: Run focused tests and prove RED**

Run:
```bash
pytest tests/test_v2_official_vendor_live.py -v
```
Expected: FAIL because `v2_official_vendor_live` does not exist.

- [ ] **Step 4: Implement the minimal reader**

Implement the interfaces above using `requests.get` injection and stdlib `html.parser.HTMLParser`. Parse only same-host index anchors plus optional same-card time/summary into the item shape accepted by `acquire_official_vendor_candidates()`; do not fetch article-detail pages.

- [ ] **Step 5: Run focused tests and existing normalizer tests**

Run:
```bash
pytest tests/test_v2_official_vendor_live.py tests/test_v2_official_vendor_acquisition.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add v2_official_vendor_live.py tests/test_v2_official_vendor_live.py
git commit -m "feat: add bounded V2 vendor live reader"
```

---

### Task 2: Add bounded GitHub releases live reader

**Files:**
- Create: `v2_github_live.py`
- Create: `tests/test_v2_github_live.py`
- Reuse: `v2_github_acquisition.py`
- Reuse: `v2_live_shadow_acquisition.py` (`SourceAcquisitionError` only)

**Interfaces:**
- Consumes: `acquire_github_candidates(...)` and existing `SourceAcquisitionError`.
- Produces:
  - `GITHUB_REPOSITORIES: tuple[str, ...]`
  - `fetch_github_repository_releases(*, repository: str, http_get: Callable[..., Any] = requests.get, token: str | None = None, timeout_seconds: float = 8.0, max_events: int = 5) -> list[dict[str, Any]]`
  - `fetch_all_github_candidates(*, http_get: Callable[..., Any] = requests.get, token: str | None = None) -> list[dict[str, Any]]`

- [ ] **Step 1: Write RED tests for exact repository allowlist and releases-only endpoint**

Assert:
- `GITHUB_REPOSITORIES` equals the three spec repositories in fixed order;
- each request is exactly `GET https://api.github.com/repos/{repo}/releases` with `params={"per_page": 5}`, timeout `8.0`;
- no tag, branch, issue, code-search, or repository-discovery request is made;
- an unallowlisted repository is rejected before network access.

- [ ] **Step 2: Write RED normalization and security tests**

With fixed JSON fixtures assert:
- release rows map to existing event shape using `id`/`tag_name`, `html_url`, `name or tag_name`, `body`, and `published_at`, with `event_kind="release"`, then flow through `acquire_github_candidates()`;
- malformed releases are dropped fail-closed;
- one repository request/HTTP/JSON failure is isolated and the remaining repositories still run;
- optional token is sent only as `Authorization: Bearer <token>`; sentinel token text never appears in returned candidates or safe exception strings;
- a response final URL outside `api.github.com` raises `SourceAcquisitionError("GitHub", "redirect_not_allowed")`;
- request/HTTP/JSON failures map only to the approved safe categories.

- [ ] **Step 3: Run focused tests and prove RED**

Run:
```bash
pytest tests/test_v2_github_live.py -v
```
Expected: FAIL because `v2_github_live` does not exist.

- [ ] **Step 4: Implement the minimal releases reader**

Implement only the interfaces above. Do not add tag/changelog fallback even though the existing normalizer supports those event kinds.

- [ ] **Step 5: Run focused tests and existing GitHub normalizer tests**

Run:
```bash
pytest tests/test_v2_github_live.py tests/test_v2_github_acquisition.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add v2_github_live.py tests/test_v2_github_live.py
git commit -m "feat: add bounded V2 GitHub live reader"
```

---

### Task 3: Build the canonical four-source live acquisition bridge

**Files:**
- Create: `v2_four_source_live.py`
- Create: `tests/test_v2_four_source_live.py`
- Reuse: `v2_source_portfolio.py`
- Reuse: `v2_live_shadow_acquisition.py`

**Interfaces:**
- Consumes:
  - `fetch_all_official_vendor_candidates(...)` from Task 1;
  - `fetch_all_github_candidates(...)` from Task 2;
  - `fetch_hacker_news_candidates(...)` and `fetch_arxiv_candidates(...)` from `v2_live_shadow_acquisition.py`;
  - `run_four_source_shadow(...)` and `SourcePortfolioConfig` from `v2_source_portfolio.py`.
- Produces:
  - `FourSourceLiveConfig(hn_limit: int = 5, arxiv_limit: int = 5, timeout_seconds: float = 8.0, max_total_candidates: int = 40)`
  - `run_four_source_live(*, deep_dive: Callable[[Mapping[str, Any]], Mapping[str, Any]], now: datetime, run_id: str, http_get: Callable[..., Any] = requests.get, github_token: str | None = None, v1_reference: str | None = None, config: FourSourceLiveConfig | None = None) -> dict[str, Any]`

- [ ] **Step 1: Write RED integration tests for exact four-source participation**

Assert a deterministic fixture run:
- builds exactly four source-family providers: `official_vendor`, `github`, `hacker_news`, `arxiv`;
- delegates final orchestration to `run_four_source_shadow()` rather than calling `run_shadow_selection()` directly;
- uses `ShadowConfig(max_candidates_per_provider=max_total_candidates, max_deep_dive_attempts=1)` and `SourcePortfolioConfig(max_total_candidates=max_total_candidates)`;
- reports `budgets.source_families` in the existing canonical order;
- preserves source-family provenance on screening entries.

- [ ] **Step 2: Write RED budget/failure-isolation tests**

Assert:
- one family exception does not prevent the other three families from contributing;
- failed family contributes zero accepted candidates and consumes no remaining total-candidate budget;
- total candidates never exceed configured `max_total_candidates`;
- HN/arXiv use the configured limit/timeout while OfficialVendor/GitHub retain their spec-fixed limits/timeouts;
- Deep Dive callback is invoked at most once;
- no rank-2 fallback occurs after rank-1 insufficiency/failure.

- [ ] **Step 3: Run focused tests and prove RED**

Run:
```bash
pytest tests/test_v2_four_source_live.py -v
```
Expected: FAIL because `v2_four_source_live` does not exist.

- [ ] **Step 4: Implement the minimal composition layer**

Use the two new live readers plus existing HN/arXiv readers to construct the four family callables; let `run_four_source_shadow()` own portfolio budgeting/ranking/Evidence delegation. Do not duplicate scoring or selection code.

- [ ] **Step 5: Run focused and portfolio regression tests**

Run:
```bash
pytest tests/test_v2_four_source_live.py tests/test_v2_source_portfolio.py tests/test_v2_live_shadow_acquisition_budget.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add v2_four_source_live.py tests/test_v2_four_source_live.py
git commit -m "feat: compose V2 four-source live acquisition"
```

---

### Task 4: Route measured V2-005 Live Proof through the four-source bridge without breaking the evidence-pack contract

**Files:**
- Modify: `v2_005_live_proof.py`
- Modify: `tests/test_v2_005_live_proof.py`
- Modify: `tests/test_v2_005_evidence_pack.py`

**Interfaces:**
- Consumes: `run_four_source_live(...)` from Task 3 and existing `GeminiEvidenceProvider` measurement semantics.
- Produces:
  - `build_live_proof(*, now: datetime, run_id: str, api_key: str, config: FourSourceLiveConfig | None = None, http_get: Callable[..., Any] = requests.get, http_post: Callable[..., Any] = requests.post, github_token: str | None = None, v1_reference: str | None = None) -> dict[str, Any]`
  - existing `write_live_proof(report, output_path) -> Path`;
  - unchanged V2-005 measurement proof version/field contract expected by `v2_005_evidence_pack.py`.

- [ ] **Step 1: Write RED route test against the current two-source implementation**

Add a test that injects/patches the acquisition boundary and requires `build_live_proof()` to call `run_four_source_live()`; explicitly fail if `build_provider_backed_observation()` remains the direct route.

- [ ] **Step 2: Write RED contract-preservation tests**

Assert a deterministic four-source proof still produces:
- `v2_005_measurement.proof_version == "V2-005"`;
- safe evaluated-candidate fields exactly equal the current six-field allowlist;
- `provider_request_count` is `0` or `1` and equals `actual_calls.deep_dive`;
- `production_mutation_authorized is False`;
- `promotion_decision == "human_review_required"`;
- current safe provider-failure categories and usage metadata behavior remain unchanged;
- four-source participation/status/count diagnostics remain outside the safe candidate object;
- serialized artifact contains none of the raw HTML/token/response sentinel strings used by the tests.

- [ ] **Step 3: Add evidence-pack compatibility regression**

Build three synthetic V2-005C reports and assert `build_evidence_pack()` accepts them without changing `PROOF_VERSION`, request-count validation, or human-only promotion semantics. Also assert unsafe candidate-field widening still fails closed.

- [ ] **Step 4: Run focused tests and prove RED**

Run:
```bash
pytest tests/test_v2_005_live_proof.py tests/test_v2_005_evidence_pack.py -v
```
Expected: new route test FAILS on the old two-source implementation.

- [ ] **Step 5: Modify `build_live_proof()` minimally**

Keep the existing recording HTTP POST / Gemini measurement wrapper. Replace only the acquisition/orchestration call so the measured proof uses `run_four_source_live()`. In `main()`, read the built-in workflow token only from `V2_GITHUB_TOKEN`; no token is required for deterministic/offline tests.

- [ ] **Step 6: Run V2-005/Evidence regression suite**

Run:
```bash
pytest tests/test_v2_005_live_proof.py tests/test_v2_005_evidence_pack.py tests/test_v2_shadow_deep_dive.py tests/test_v2_shadow_provider_diagnostics.py tests/test_v2_shadow_provider_http_diagnostics.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add v2_005_live_proof.py tests/test_v2_005_live_proof.py tests/test_v2_005_evidence_pack.py
git commit -m "feat: measure V2 four-source live proof"
```

---

### Task 5: Preserve the ChatOps/workflow safety contract and complete repository verification

**Files:**
- Modify: `.github/workflows/v2-shadow-deep-dive.yml`
- Modify: `tests/test_v2_shadow_deep_dive_workflow.py`
- Modify if required by freshness guard: `AI_Intelligence_Factory_最終仕様書.md`
- Modify if required by repository classification guard: `member_customer_surface_contract.py`

**Interfaces:**
- Consumes: unchanged Issue #71 command `/aiif run v2_shadow_deep_dive` and confirmation token `RUN_V2_SHADOW_DEEP_DIVE`.
- Produces: same workflow artifact `article_audit/v2_shadow_deep_dive.json`, retention 14 days, using the four-source V2-005C implementation on `main` after merge.

- [ ] **Step 1: Write RED workflow contract tests**

Require:
- existing exact ChatOps command and hard-mapped workflow payload remain unchanged;
- workflow remains `workflow_dispatch` only, with no `schedule`, `push`, or `workflow_run` provider trigger;
- permissions remain `contents: read` only;
- `GEMINI_API_KEY` remains the only repository secret referenced by the provider-backed workflow;
- workflow exports exactly `V2_GITHUB_TOKEN: ${{ github.token }}` for the live-proof process; `GH_PAT` remains absent from this downstream workflow;
- workflow runs `tests/test_v2_official_vendor_live.py`, `tests/test_v2_github_live.py`, `tests/test_v2_four_source_live.py`, and the existing V2-005 safety suites before live execution;
- artifact path and 14-day retention remain unchanged.

- [ ] **Step 2: Run workflow test and prove RED**

Run:
```bash
pytest tests/test_v2_shadow_deep_dive_workflow.py -v
```
Expected: FAIL because current workflow does not yet export `V2_GITHUB_TOKEN` or include the V2-005C focused tests.

- [ ] **Step 3: Update workflow minimally**

Pass `V2_GITHUB_TOKEN: ${{ github.token }}` only to the bounded provider-backed observation step, add the new focused test modules to the safety test step, and change no trigger/permission/confirmation/artifact contract.

- [ ] **Step 4: Run focused V2-005C suite**

Run:
```bash
pytest -q \
  tests/test_v2_official_vendor_live.py \
  tests/test_v2_official_vendor_acquisition.py \
  tests/test_v2_github_live.py \
  tests/test_v2_github_acquisition.py \
  tests/test_v2_four_source_live.py \
  tests/test_v2_source_portfolio.py \
  tests/test_v2_005_live_proof.py \
  tests/test_v2_005_evidence_pack.py \
  tests/test_v2_shadow_deep_dive.py \
  tests/test_v2_shadow_provider_diagnostics.py \
  tests/test_v2_shadow_provider_http_diagnostics.py \
  tests/test_v2_shadow_deep_dive_workflow.py
```
Expected: PASS.

- [ ] **Step 5: Run full deterministic repository tests**

Run:
```bash
pytest -q
```
Expected: all tests PASS; only pre-existing warnings are acceptable.

- [ ] **Step 6: Run repository guards**

Run the repository's canonical commands/workflows for:
- P0-B Offline Verification;
- Integration Reconciliation CI;
- Repository-wide Falsification Guard;
- Notion Access Policy Guard;
- Workflow Reference Guard;
- Integration Stability Guard;
- `git diff --check origin/main...HEAD`.

Expected: all GREEN/PASS.

- [ ] **Step 7: Resolve only guard-required governance updates**

If the specification freshness fingerprint or non-member classification guard fails solely because of the new V2 shadow files/workflow bytes, update only the exact canonical fingerprint/classification required by the guard. Do not widen Production semantics.

- [ ] **Step 8: Re-run affected guards after any governance update**

Expected: all GREEN/PASS on the exact final head.

- [ ] **Step 9: Commit final workflow/governance changes**

Stage only files that actually changed:
```bash
git add .github/workflows/v2-shadow-deep-dive.yml tests/test_v2_shadow_deep_dive_workflow.py
# If and only if guard-required:
git add AI_Intelligence_Factory_最終仕様書.md member_customer_surface_contract.py
git commit -m "chore: wire V2-005C live proof workflow"
```

- [ ] **Step 10: Stop before merge/live proof**

Create/update the implementation PR as Draft, record exact final head and GREEN verification evidence, and wait for explicit `MERGE GO`. Do not run the 3–5 Live Proof series before merge.

---

## Post-merge operational proof (not implementation work)

After explicit `MERGE GO` and merge to `main`:

1. Trigger `/aiif run v2_shadow_deep_dive` through Issue #71 only.
2. Run 3 independent proofs first; run at most 2 more only if needed, maximum 5.
3. Verify each artifact proves all four source families were attempted, provider request count <= 1, `production_authority="v1"`, `production_mutation_authorized=false`, and human-only promotion.
4. Stop the series immediately on any P0 invariant violation.
5. Aggregate 3–5 artifacts with `v2_005_evidence_pack.py`.
6. Human-review source participation, topic value, Evidence quality, provider reliability, token usage/cost, and V1 comparison where available.
7. Owner explicitly decides Gate A; only then may V2-006 begin.
