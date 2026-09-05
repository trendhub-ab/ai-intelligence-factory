# Run244 — Decision / Evidence / Product Review Protocol Modularization

## Purpose

Run244 continues the `pipeline.py` strangler modularization after Run243 without changing Production behavior, provider usage, quality thresholds, quotas, persistence destinations, or public-release policy.

The extraction is intentionally limited to deterministic/provider-free protocol shaping. Side-effectful execution remains owned by `pipeline.py`.

## Physical slimming

- Run243 postimage: **10,840 lines**
- Run244 postimage: **10,434 lines**
- Net reduction: **406 lines**

This is a maintainability/change-risk improvement. It is not evidence that Production E2E runtime became faster; external I/O and model latency still dominate real execution time.

## Canonical ownership after Run244

### `evidence_sufficiency.py`

Owns deterministic Evidence-to-Decision sufficiency classification previously implemented by `assess_evidence_sufficiency()` in `pipeline.py`.

The pipeline wrapper supplies the live future-source pattern, evidence URL normalization callback, and existing SUFFICIENT / SUPPLEMENT_REQUIRED / INSUFFICIENT constants at call time.

### `content_generation_protocol.py`

Run243 already owned deterministic article-generation/editorial protocol. Run244 additionally makes `build_decision_prompt()` canonical here.

The pipeline wrapper continues to bind live:

- engagement labels
- evidence context limits
- source-context truncation
- Source-specific Fact Discipline
- Human Editorial / Reader Experience rules
- article display variant selection
- section split token
- JST/current-date behavior

No Gemini call is moved into this module.

### `product_review_protocol.py`

Owns provider-free Product Review protocol only:

- Product Review prompt shaping
- schema error / strict integer validation
- payload validation
- UI-only Japanese display-label normalization
- deterministic JSON wrapper cleanup/parser
- provider parsed/text response normalization
- existing Technology-state-to-repo rehydration

The module has no Gemini/provider SDK, network client, Notion API, filesystem persistence, or GitHub persistence call site.

## Explicitly retained in `pipeline.py`

Run244 does **not** move or modify side-effectful/high-risk ownership. In particular, these remain pipeline-owned:

- `generate_intelligence_report()`
- Gemini/model invocation and model-pool fallback
- `_call_product_review_pool()`
- `select_product_review_candidates()` and its current Decision Intelligence lookup behavior
- `run_product_reviews()`
- source-network acquisition / SSRF boundaries
- Notion query/write/persistence
- Pending Retry fail-safe handling
- Fact / Evidence / Decision / Publication / Human Appeal gate execution
- request budgets, persistent counters, pacing and retry policy

## Fail-closed migration contract

`run244_decision_product_protocol_migration.py` accepts only the exact Run243 **10,840-line** preimage and the exact historical top-level function sizes:

- `assess_evidence_sufficiency`: 116
- `build_decision_prompt`: 163
- `_product_review_prompt`: 21
- `_product_review_schema_error`: 2
- `_strict_schema_int`: 8
- `_validate_product_review_payload`: 62
- `_normalize_japanese_display_label`: 20
- `_decode_product_review_json`: 20
- `_parse_product_review_response`: 17
- `_parse_product_review_model_response`: 10
- `_technology_state_to_repo`: 52

Unexpected source shape, function size, import anchor, or ownership aborts without rewriting. The post-migration state is idempotent.

## Dedicated falsification

Run244 adds:

- `tests/test_run244_decision_product_protocol_module.py` — **11 tests**
- `tests/test_run244_decision_product_protocol_integration.py` — **7 tests**

Dedicated total: **18/18 passed** during guarded migration validation.

The tests cover provider/network/persistence-free module ownership, evidence fail-closed behavior, Product Review schema/score invariants, bool-vs-integer strictness, UI-only label safety, deterministic JSON parsing, Technology-state identity binding, live pipeline callback binding, physical slimming, and preservation of side-effectful pipeline ownership.

Historical Run243's stdlib-only ownership test was reconciled to permit `json` because Run244 moves `build_decision_prompt()` into the same canonical stdlib-only module. The provider/I/O prohibition remains unchanged.

Adjacent guarded migration regressions also passed for:

- Run243 content-generation protocol
- Run134 monthly Decision Brief
- Decision Intelligence
- Revenue Product Phase2
- migration idempotency / `git diff --check`

Final PR CI/full pytest/Synthetic results must be taken from the final PR head; the guarded migration result alone is not a substitute for main-based PR validation.

## Protected Production contracts unchanged

Run244 changes none of the following:

- Gemini model pool or fallback order
- Gemini call-site count
- RPD / RPM / TPM
- persistent daily counter
- pacing or retry budgets
- Deep Dive / Pending Retry / Product Review request budgets
- Fact / Evidence / Decision / Publication / Human Appeal thresholds or blocking semantics
- Screening threshold / Stock eligibility / Decision Score / portfolio budget
- Notion schema or canonical destinations
- subscriber PII handling
- Daily **PAUSED** state
- public note release **human-only** policy

## Production source of truth

Run244 remains a PR candidate until explicitly merged. `main` remains Production Source of Truth at all times.