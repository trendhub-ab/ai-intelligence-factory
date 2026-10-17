# V2 Source Acquisition Reliability + Gold-label Benchmark Design

Date: 2026-10-17
Status: Design review
Base main: `2ede3883bc26f697575ef0cc3f5f1df92322152d`

## 1. Purpose

This change addresses two independent V2 quality risks without changing V1 Production authority:

1. External acquisition sources can fail transiently (timeout, connection error, HTTP 429, HTTP 5xx). This risk is not specific to ArXiv; it applies to OfficialVendor, GitHub, HackerNews, and ArXiv.
2. Semantic Screening now discriminates candidates, but there is no stable offline benchmark for measuring whether future prompt/model changes improve or regress Precision / Recall / F1.

The implementation must remain bounded, cheap, shadow-only, and fail-soft at source level while preserving fail-closed behavior for Evidence and Production isolation.

## 2. Existing behavior

### 2.1 Source portfolio

V2 uses four required acquisition families:

- OfficialVendor
- GitHub
- HackerNews
- ArXiv

A single source failure is isolated and the remaining sources continue. However, the HTTP behavior is inconsistent across readers:

- OfficialVendor has natural redundancy across three vendor collection pages, but each GET has no retry.
- GitHub has natural redundancy across three repositories, but each GET has no retry.
- HackerNews top-stories acquisition is a single source-level request; item-level failures are already skipped individually.
- ArXiv is a single source-level GET; one transient failure yields zero ArXiv candidates.

The common selection layer currently records provider failures mostly by exception class name, losing useful safe categories such as timeout vs 429 vs 5xx.

### 2.2 Semantic benchmark gap

Semantic Screening evaluates four booleans:

- `ai_relevant`
- `decision_value`
- `change_novelty`
- `applied_reader_value`

The live discrimination fix from PR #808 prevents saturated all-positive output from being accepted blindly, but there is no canonical labeled dataset and no offline metric runner.

## 3. Goals

### 3.1 Acquisition reliability

Create one shared V2 acquisition reliability contract that all four source families can use.

Required properties:

- classify failures into safe categories;
- retry only transient failures;
- maximum one retry per logical HTTP read;
- no unbounded loops;
- no model calls;
- no Production writes;
- one failed source must not stop the other sources;
- preserve existing per-source allowlists, limits, and read-only behavior;
- expose bounded diagnostic metadata without raw response bodies, tokens, credentials, or secrets.

### 3.2 Gold-label benchmark

Create a provider-free offline benchmark contract that can score Semantic Screening predictions against human-approved labels.

Required metrics:

- per-dimension TP / FP / TN / FN;
- per-dimension Precision / Recall / F1;
- macro Precision / Recall / F1;
- exact-match accuracy across all four booleans;
- all-positive saturation rate;
- evaluated sample count.

CI must not call Gemini. A future manual provider-backed benchmark may feed predictions into the same evaluator, but the evaluator itself must be deterministic and offline.

## 4. Non-goals

This change must not:

- change V1 Production model routing or authority;
- change article generation, Ready, Notion, note, eyecatch, or publication flows;
- add new external discovery sources;
- turn transient retry into general fallback between unrelated sources;
- retry permanent client/configuration failures;
- increase Semantic model-family budget or Evidence model-family budget;
- auto-create or auto-modify Gold labels from model output;
- claim real-world classification accuracy without a reviewed Gold dataset.

## 5. Acquisition reliability design

### 5.1 Shared failure taxonomy

Introduce a V2 acquisition diagnostic taxonomy with these categories:

- `timeout`
- `connection`
- `http_429`
- `http_5xx`
- `http_4xx`
- `invalid_payload`
- `invalid_json`
- `invalid_xml`
- `invalid_html`
- `redirect_host_unapproved`
- `request_failure`
- `unknown_failure`

Existing source-specific exceptions may remain, but each must expose or be translated to a safe category.

### 5.2 Retry policy

Retryable:

- timeout;
- connection error;
- HTTP 429;
- HTTP 5xx.

Non-retryable:

- HTTP 4xx except 429;
- invalid payload / JSON / XML / HTML;
- unapproved redirect host;
- allowlist/configuration violations.

Budget:

- first attempt + at most one retry;
- maximum two HTTP attempts per logical read;
- retry delay must be bounded and injectable for tests;
- default delay should be short and source-neutral; source-specific policy may override only when an upstream contract requires it.

The retry layer must not retry an entire provider portfolio when only one bounded logical read failed unless the existing reader already models that read independently.

### 5.3 Integration by source

#### OfficialVendor

Keep the three existing collection pages and existing `all_sources_failed` behavior. Apply the shared retry policy to each individual collection-page GET. Do not retry the full three-source loop.

#### GitHub

Keep the three allowlisted repositories and existing `all_repositories_failed` behavior. Apply the shared retry policy to each releases GET. Do not retry the full repository loop.

#### HackerNews

Apply the shared retry policy to the top-stories request. Keep item-level failure isolation. Item GETs may use the same bounded retry helper only if doing so does not violate the existing acquisition budget; no item may exceed two HTTP attempts.

#### ArXiv

Apply the shared retry policy to the single API query. Preserve the same query, result limit, GET-only behavior, and XML parsing contract.

### 5.4 Safe telemetry

Each source-family status should preserve existing success/failure fields and add bounded diagnostics where available:

- `attempt_count`
- `retry_used`
- `first_failure_category`
- `final_failure_category`

For multi-read families (OfficialVendor, GitHub, HackerNews item reads), detailed per-read telemetry should remain internal unless already exposed safely; the top-level Artifact needs only source-level aggregate diagnostic values.

Never include:

- raw body;
- request headers containing credentials;
- tokens;
- API keys;
- secret URLs with credentials;
- exception messages that may contain sensitive transport details.

### 5.5 Failure semantics

Source acquisition remains fail-soft:

- one source family may fail;
- other source families continue;
- candidate budget is consumed only by accepted candidates;
- no source retry may trigger Production mutation;
- V2 can continue with fewer than four sources for shadow observation, while the Artifact must make the degraded source state explicit.

This design does not turn source acquisition into a hard gate for V2 Shadow completion.

## 6. Gold-label benchmark design

### 6.1 Dataset contract

Add a versioned JSON dataset under a V2-owned test/benchmark path. Each record must contain:

- stable `case_id`;
- `title`;
- `description`;
- optional `source_family` for context only;
- Gold booleans for the four Semantic dimensions;
- concise human rationale;
- label provenance/version metadata.

The evaluator must ignore source family as a correctness shortcut; labels are judged from the textual evidence contract used by Semantic Screening.

### 6.2 Seed dataset

The initial dataset should contain a deliberately mixed set, including:

- clear non-AI negatives;
- AI-adjacent but non-decision-value items;
- low-information HackerNews-style rows;
- concrete AI model/release/API changes;
- safety/policy/education items where some dimensions are true and others false;
- ambiguous cases whose correct default is false under the conservative Semantic contract.

The initial seed is a regression benchmark, not a statistically representative corpus. Its purpose is to prevent obvious prompt/model regressions.

### 6.3 Prediction contract

The evaluator accepts predictions keyed by `case_id`, each containing exactly the same four booleans.

Contract errors are fail-closed for benchmark execution:

- missing case;
- extra case;
- non-boolean field;
- missing field;
- duplicate case ID.

### 6.4 Metric definitions

For each dimension:

- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = harmonic mean of Precision and Recall

Zero-denominator behavior must be explicit and deterministic; use `0.0` rather than NaN.

Macro metrics are arithmetic means across the four dimensions.

Exact-match accuracy is the proportion of samples whose four predicted booleans exactly equal the four Gold booleans.

All-positive saturation rate is the proportion of samples predicted `true` for all four dimensions.

### 6.5 CI behavior

CI runs only:

- dataset schema validation;
- evaluator unit tests;
- fixed synthetic prediction fixtures;
- metric regression tests.

CI must make zero Gemini/provider calls.

A manual provider-backed benchmark may be added later or as a separate explicit workflow. It must not be a required merge check and must reuse the same offline evaluator.

## 7. Test strategy

### 7.1 Acquisition RED tests

Before implementation, add tests proving current behavior lacks the contract:

- timeout does not recover on retry;
- HTTP 429 does not recover on retry;
- HTTP 503 does not recover on retry;
- HTTP 400 is not retried;
- invalid XML/JSON/HTML is not retried;
- safe diagnostic category is preserved to top-level provider status;
- no logical read exceeds two attempts;
- failure of one source does not stop remaining sources.

### 7.2 Benchmark RED tests

Add tests for:

- exact known confusion matrix;
- zero-denominator handling;
- macro metrics;
- exact-match accuracy;
- saturation rate;
- malformed prediction contract rejection;
- dataset duplicate-ID rejection;
- provider-free execution.

### 7.3 Regression

Verification order:

1. focused acquisition/benchmark tests;
2. V2 provider-free test suite;
3. full pytest;
4. Repository-wide Falsification Guard;
5. P0-B Offline Verification;
6. Synthetic Production smoke / production-write isolation.

No provider-backed live run is required before merge unless the code changes cannot be validated hermetically. After merge, one V2 Shadow run is appropriate to observe telemetry without deliberately inducing upstream failures.

## 8. Cost and performance guardrails

- Healthy path remains one HTTP attempt per logical read.
- Transient failure path adds at most one extra HTTP attempt for that logical read.
- No extra Gemini calls.
- No new paid provider.
- No Production writes.
- Retry delay remains bounded and must not create long-running workflows.

## 9. Rollout

1. Implement shared reliability helper and tests.
2. Integrate source readers one by one without changing source allowlists or limits.
3. Surface safe top-level diagnostics.
4. Add offline Gold dataset and evaluator.
5. Run full regression/guards.
6. Merge only after explicit MERGE GO.
7. Post-merge, run one V2 Shadow observation and verify healthy-path behavior and safe telemetry.

## 10. Acceptance criteria

The work is complete only when all of the following are true:

- all four source families use the same retryability rules;
- transient failures are retried at most once;
- permanent/contract failures are not retried;
- source failure isolation remains intact;
- Artifact diagnostics distinguish safe failure categories;
- no secrets/raw bodies are emitted;
- healthy-path HTTP/model budgets do not increase;
- Semantic/Evidence model budgets are unchanged;
- Gold dataset is human-authored/versioned and model output cannot mutate it;
- evaluator reports per-dimension and macro Precision / Recall / F1, exact-match accuracy, and saturation rate;
- CI benchmark evaluation is provider-free;
- full test suite and Production-isolation guards remain GREEN;
- main is not modified without explicit merge approval.
