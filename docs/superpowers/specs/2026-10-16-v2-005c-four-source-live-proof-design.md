# AI Intelligence Factory V2-005C — Four-Source Live Proof Design

Date: 2026-10-16
Status: Design specification — awaiting user review
Base Production main: `686cf66cc8f93f379ee05f15fb4fa83a0d85a5ef`
Design branch: `design/v2-005c-four-source-live-proof-20261016`

## 1. Purpose

V2-005C closes the remaining proof gap between the merged V2-005B four-source portfolio and the existing V2-005 measured Live Proof workflow.

The current repository already contains:

- V2-005 measured provider-backed Live Proof;
- V2-005A Selection Value ranking;
- V2-005B four-source shadow orchestration for OfficialVendor, GitHub, Hacker News, and ArXiv;
- provider-safe Gemini Evidence with one-request budget, retry 0, fallback 0;
- fail-closed diagnostic artifacts and V1 Production authority.

However, the production-safe Live Proof entrypoint still calls the older Hacker News / ArXiv acquisition path. The OfficialVendor and GitHub adapters currently normalize already-fetched data but do not themselves perform live retrieval. Therefore the repository cannot yet produce the required 3–5 independent four-source Live Proof artifacts promised by V2-005B.

V2-005C adds only the missing read-only live acquisition and orchestration bridge needed to prove the four-source design. It does not grant V2 any Production mutation authority.

## 2. Success criteria

V2-005C is complete only when all of the following are true:

1. A single manually initiated shadow run can read all four approved source families:
   - OfficialVendor;
   - GitHub;
   - Hacker News;
   - ArXiv.
2. The four families flow through the existing `run_four_source_shadow()` orchestration.
3. Only rank #1 may enter Gemini Evidence.
4. Gemini Evidence remains bounded to at most one request per run.
5. Retry remains 0.
6. Model fallback remains 0.
7. Rank fallback remains 0.
8. V1 remains the sole Production authority.
9. No Notion, note, Ready, delivery-ledger, subscriber, Economic State, publication, or public-release mutation is possible from this path.
10. The Live Proof artifact records enough safe diagnostics to review source participation, candidate counts, rank #1, Evidence result, provider call count, and mutation authority.
11. Three to five independent post-merge Live Proof runs can be aggregated by the existing V2-005 evidence-pack path for explicit human review before V2-006.

## 3. Non-goals

V2-005C does not:

- build V2-006 Article Brief;
- build Writer or quality-gate logic;
- connect V2 to Daily, Fresh, Rolling Re-review, Notion, note, or Ready delivery;
- change Selection Value scoring;
- change the Evidence eligibility threshold;
- add another source family;
- use X as a direct candidate source;
- restore Product Hunt;
- add retries, hidden fallbacks, rank-2 rescue, or automatic promotion;
- add any Lite model;
- change V1 Production behavior;
- use model calls to compensate for acquisition or orchestration defects.

## 4. Architectural principle

V2-005C follows one rule:

> **Fetch narrowly, normalize deterministically, rank once, evaluate once, mutate nothing.**

The existing V2-005B four-source orchestration remains the only integration point for the four source families. V2-005C must not create a second ranking or source-merging path.

The intended data flow is:

`Manual ChatOps -> V2 Live Proof Workflow -> Four bounded GET-only source providers -> Existing V2 source adapters -> run_four_source_shadow() -> Selection Value ranking -> rank #1 -> Gemini Evidence x1 max -> measured diagnostic artifact -> offline evidence pack -> human Gate A decision`

## 5. Components

### 5.1 OfficialVendor live reader

Add one small read-only acquisition layer in front of the existing `acquire_official_vendor_candidates()` normalizer.

Responsibilities:

- fetch only from the exact initial endpoint allowlist in Section 6.1;
- allow HTTP GET only;
- enforce exact host/domain matching before and after redirects;
- use an 8-second request timeout;
- enforce a maximum of 5 index items per vendor before normalization;
- parse only the supported bounded HTML-index contract for the three initial vendor collection pages;
- perform no article-detail fetch during acquisition;
- return already-bounded item mappings to `acquire_official_vendor_candidates()`;
- classify failures with safe categorical reason codes;
- never persist raw response bodies, cookies, authorization headers, or transport exception text.

The initial live reader must not perform search-engine discovery, site crawling, arbitrary feed discovery, sitemap expansion, browser automation, or runtime URL injection.

### 5.2 GitHub live reader

Add one read-only acquisition layer in front of the existing `acquire_github_candidates()` normalizer.

Responsibilities:

- query only the exact repositories in Section 6.2;
- use GitHub REST GET endpoints only;
- for V2-005C proof, read releases only via `/repos/{owner}/{repo}/releases`;
- request at most 5 releases per repository;
- preserve stable repository order: OpenAI, Anthropic, Google;
- use the existing workflow's `contents: read` authority only;
- use `github.token` only if required for reliable REST reads, with no permission expansion;
- never copy the token into artifacts or logs;
- reject repositories, hosts, event kinds, or URLs outside the allowlist;
- fail one repository independently without aborting the remaining four-source run.

The existing normalizer may continue to support `release`, `tag`, and `changelog`, but V2-005C live proof introduces no tag/changelog fallback. No GitHub-wide search, issue discovery, arbitrary code search, repository writes, release writes, or elevated permissions are permitted.

### 5.3 Existing Hacker News and ArXiv readers

Reuse the already-proven bounded V2 live acquisition logic.

Do not fork or reimplement the existing HN/arXiv readers merely to fit V2-005C. If an adapter shape mismatch is found, add the minimum compatibility wrapper at the four-source boundary.

### 5.4 Four-source Live Proof bridge

Modify the measured V2-005 Live Proof entrypoint so the production-safe manual workflow can invoke the exact four-source portfolio.

The bridge must:

- construct exactly the four approved source-family providers;
- call `run_four_source_shadow()`;
- retain the current V2-005 measurement wrapper semantics;
- capture the evaluated rank-1 candidate using the existing safe-field allowlist;
- preserve numeric Gemini usage metadata when available;
- preserve `production_mutation_authorized = false`;
- preserve `promotion_decision = "human_review_required"`;
- preserve at-most-one Gemini request.

The bridge must not duplicate selection, ranking, or Evidence logic.

### 5.5 Workflow

Reuse the existing manual `v2-shadow-deep-dive.yml` workflow and existing Issue #71 ChatOps route.

Required workflow properties:

- manual/ChatOps initiated only;
- no schedule;
- no push-triggered provider call;
- `contents: read` only;
- existing confirmation token remains required;
- Gemini credential remains only in the provider-backed job boundary;
- GitHub token, if needed for GitHub REST reads, uses only the built-in read-only workflow token;
- no Notion, note, browser, subscriber, publication, or delivery credentials are introduced;
- artifact retention remains bounded;
- concurrency continues to protect Gemini request budget.

## 6. Initial source allowlist

The V2-005C proof series uses the following fixed initial allowlist. Runtime input cannot add or replace these sources.

### 6.1 OfficialVendor collection pages

Initial vendor order is fixed:

1. OpenAI
   - collection URL: `https://openai.com/news`
   - exact allowed hostname: `openai.com`
   - parser: bounded HTML index
   - max index items: 5
   - timeout: 8 seconds
2. Anthropic
   - collection URL: `https://www.anthropic.com/news`
   - exact allowed hostname: `www.anthropic.com`
   - parser: bounded HTML index
   - max index items: 5
   - timeout: 8 seconds
3. Google Gemini
   - collection URL: `https://blog.google/products-and-platforms/products/gemini/`
   - exact allowed hostname: `blog.google`
   - parser: bounded HTML index
   - max index items: 5
   - timeout: 8 seconds

The reader may extract only bounded index metadata needed by the existing candidate contract: stable article URL, title, date when available, and short index summary when available. It must not fetch the linked article body during V2-005C acquisition.

If a vendor changes its HTML so the exact parser contract no longer holds, that vendor fails safely for the run. The implementation must not add a browser fallback, generic scraper, search engine, or alternate URL automatically.

### 6.2 GitHub repositories

Initial repository order is fixed:

1. `openai/openai-python`
2. `anthropics/anthropic-sdk-python`
3. `googleapis/python-genai`

For each repository, V2-005C reads only the GitHub releases collection, max 5 releases. No tag fallback, branch scan, issue scan, code search, or repository discovery is allowed.

Adding or changing an OfficialVendor URL or GitHub repository after V2-005C requires a reviewed code/config change; it cannot be supplied through workflow input, Issue comment, environment variable, or model output.

## 7. Budgets

V2-005C keeps all budgets explicit.

- source families: exactly 4;
- OfficialVendor collection pages: exactly 3 initial vendors;
- GitHub repositories: exactly 3 initial repositories;
- OfficialVendor max index items: 5 per vendor before family-level portfolio bounding;
- GitHub max releases: 5 per repository before family-level portfolio bounding;
- OfficialVendor/GitHub network timeout: 8 seconds per GET;
- total candidate budget: existing `SourcePortfolioConfig` default unless a separate reviewed config narrows it;
- per-provider candidate budget: existing `ShadowConfig` contract;
- network method: GET only for source acquisition;
- Gemini Evidence requests: max 1 per run;
- Gemini retry: 0;
- Gemini model fallback: 0;
- rank fallback: 0;
- Production writes: 0;
- Notion writes: 0;
- note writes: 0.

One source failing must not consume the remaining source families' candidate budget.

## 8. Fail-closed behavior

The following conditions fail safely rather than widening behavior:

- unapproved source endpoint;
- unapproved GitHub repository;
- unsupported response content type or schema;
- malformed source item;
- redirect to an unapproved hostname;
- GitHub event outside the supported event allowlist;
- total candidate budget exceeded;
- more than one Evidence request attempted;
- ambiguous rank #1;
- missing or malformed Evidence contract;
- Production mutation marker not exactly false;
- secret/raw-provider material detected in the artifact.

A single source network failure is not itself a full-run failure. It is recorded as a safe source-level failure and the remaining approved sources continue within their existing budgets.

If a safety invariant is violated, the proof series stops. The implementation must not silently retry, add a fallback source, widen an allowlist, or rescue with rank #2.

## 9. Observability and artifact contract

Each Live Proof artifact must make human review possible without leaking sensitive data.

At minimum record:

- proof version;
- run ID;
- source-family list;
- per-source status;
- per-source acquired and accepted candidate counts;
- total candidate count;
- rank #1 safe candidate fields;
- Selection Value score/reasons already permitted by the V2 report contract;
- Evidence attempted count;
- provider request count;
- safe provider failure category, if any;
- token usage metadata when valid and available;
- V1 comparison state when available;
- `production_authority = "v1"`;
- `production_mutation_authorized = false`;
- `promotion_decision = "human_review_required"`.

Do not persist:

- API keys or tokens;
- authorization headers;
- prompts;
- raw Gemini response bodies;
- raw transport exception text;
- arbitrary HTML/page dumps;
- browser cookies/session state;
- unpublished note/Notion content.

## 10. Testing strategy

Implementation must follow TDD.

### Layer 1 — reader contracts

Write RED tests first for:

- GET-only enforcement;
- exact endpoint/repository allowlists;
- timeout and item caps;
- redirect/host rejection;
- malformed payload fail-closed behavior;
- safe error classification;
- no secret/raw-response leakage;
- deterministic normalization.

OfficialVendor fixture tests must model the exact three collection-page parser contracts without making network calls. GitHub fixture tests must model the releases endpoint response for the exact three repositories.

### Layer 2 — four-source integration

Write RED tests proving the current `v2_005_live_proof.py` still uses the old two-source path, then require the new bridge to:

- invoke exactly four source-family providers;
- preserve the existing total candidate budget;
- continue remaining sources after one source fails;
- keep source-family provenance;
- permit only one rank-1 Evidence attempt;
- never rescue rank #2.

### Layer 3 — workflow contract

Write RED workflow tests requiring:

- existing ChatOps command/confirmation remains unchanged;
- manual-only trigger;
- read-only permissions;
- no Production credentials;
- four-source V2-005C entrypoint;
- built-in GitHub token only if the read-only releases client needs it;
- bounded artifact retention;
- no retry/fallback expansion.

### Layer 4 — repository verification

Before merge:

- focused tests;
- relevant V2 acquisition/selection/Evidence tests;
- full repository pytest;
- P0-B Offline Verification;
- Integration Reconciliation CI;
- Repository-wide Falsification Guard;
- Notion Access Policy Guard;
- Workflow Reference Guard;
- `git diff --check`.

No live provider call is required to make the implementation PR green.

## 11. Post-merge Live Proof protocol

After explicit `MERGE GO` and merge to main:

1. trigger only through the existing Issue #71 ChatOps command for V2 provider-backed shadow evidence;
2. run 3 independent proofs first;
3. if the 3 runs are operationally valid and sufficiently varied, stop at 3; otherwise run at most 2 additional proofs, for a maximum of 5;
4. each run may use at most one Gemini Evidence request;
5. retry remains 0 and fallback remains 0;
6. download and verify each artifact;
7. aggregate 3–5 artifacts using the existing V2-005 evidence-pack path;
8. manually review source participation, topic value, Evidence quality, provider reliability, token usage, and V1 comparison where available;
9. make an explicit human Gate A decision on whether to proceed to V2-006.

A successful GitHub Actions status alone does not pass Gate A.

## 12. Cost discipline

V2-005C should reduce uncertainty without creating a new recurring cost center.

- source acquisition uses public/read-only HTTP only;
- deterministic parsing/ranking is preferred over model use;
- only rank #1 reaches Gemini;
- at most 3 Gemini calls are expected for the minimum proof series, at most 5 for the full series;
- no call is made merely to compensate for source failure;
- no retry is permitted;
- monetary cost is evaluated after the proof using measured token usage and then-current official pricing, not hard-coded into runtime logic.

## 13. Files expected to change during implementation

Likely implementation scope:

- create one OfficialVendor bounded live-reader module;
- create one GitHub releases live-reader module;
- create or modify one four-source acquisition composition layer if necessary to keep vendor/repository aggregation outside the selector;
- modify `v2_005_live_proof.py` to call the four-source portfolio;
- modify `.github/workflows/v2-shadow-deep-dive.yml` only as needed to expose the built-in read-only GitHub token and invoke V2-005C;
- add focused tests for both readers, four-source Live Proof integration, safety boundaries, and workflow contract;
- update canonical Production specification/fingerprint only if required by the existing freshness guard.

Do not modify V1 `pipeline.py`, V1 publication authority, Notion/note writers, Ready delivery, or subscriber/member mutation paths.

## 14. Promotion gate

V2-005C does not itself authorize V2-006.

Gate A passes only when the owner explicitly approves the 3–5-run evidence pack after reviewing:

- whether the four-source portfolio produces higher-value candidates;
- whether primary-source traceability is adequate;
- whether one Evidence call is sufficient;
- whether provider reliability is acceptable;
- whether the measured API cost is justified;
- whether any P0 safety invariant was violated;
- whether V2's candidate quality is better than, equivalent to, or worse than V1 where comparison is possible.

Any P0 invariant violation blocks promotion regardless of article/topic quality.

## 15. Definition of done

V2-005C is done when:

- the implementation is merged after explicit approval;
- the four approved live source families are genuinely exercised through the canonical four-source shadow path;
- 3–5 independent bounded Live Proof artifacts exist;
- all runs prove zero Production mutation authority;
- Gemini request budget is never exceeded;
- the evidence pack is generated and manually reviewed;
- the owner explicitly decides whether Gate A passes and whether V2-006 may begin.

Until then, V2-005B remains implemented but not fully proven in live four-source operation.
