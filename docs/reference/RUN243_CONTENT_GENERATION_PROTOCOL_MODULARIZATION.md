# Run243 — Content Generation Protocol Modularization

## Purpose

Continue the Run231 strangler modularization without changing Production decisions, model usage, quality thresholds, persistence or publication policy.

Run243 extracts five deterministic presentation/protocol functions from `pipeline.py` into `content_generation_protocol.py`:

- source-specific Fact Discipline prompt rules
- Human Editorial / Reader Experience prompt rules
- Gemini response parsing and management/article separation
- conservative plain-text section-title promotion
- monthly Digest Markdown shaping

The 845-line `generate_intelligence_report()` orchestration, Gemini invocation, Fact/Evidence/Decision/Publication/Human Appeal gate execution and Notion persistence deliberately remain outside this extraction.

## Physical result

- Run242 preimage: **11,172 lines**
- Run243 postimage: **10,840 lines**
- net `pipeline.py` reduction: **332 lines**

This is a maintainability/change-risk improvement. It is not evidence that Production E2E latency improved; runtime bottlenecks continue to be measured by `run231_performance_telemetry.py`.

## Canonical ownership

`content_generation_protocol.py` is stdlib-only and has no provider, network, persistence, environment or credential access.

Direct canonical aliases:

- `_source_fact_discipline`
- `_human_editorial_style_rules`
- `_promote_plaintext_section_titles`

Thin live-binding wrappers remain in `pipeline.py` for:

- `_parse_gemini_response()` — injects the live section token and existing parsing callbacks
- `build_monthly_digest_markdown()` — injects the live Deep Dive / Ready / Stocked status constants

This preserves historical monkeypatch/runtime behavior while moving the heavy deterministic bodies out of the monolith.

## Fail-closed migration governance

`run243_content_generation_protocol_migration.py` accepts only the exact Run242 11,172-line preimage and exact historical function sizes. Unexpected headers, ownership, import anchors or line counts abort without rewriting the pipeline.

The migration is idempotent after the canonical postimage is present.

## Protected Production contracts

Run243 does **not** change:

- Gemini model, fallback order, prompt-call count or model invocation site
- RPD/RPM/TPM limits, persistent daily counter, pacing or retry budgets
- Deep Dive / Pending Retry / Product Review request limits
- Fact, Evidence, Decision, Publication or Human Appeal thresholds/blocking semantics
- Screening thresholds, Stock eligibility, Decision Score formula or Deep Dive portfolio budget
- Notion schemas, canonical destinations or member-product routing
- subscriber PII handling
- Daily workflow PAUSED state
- public note release human-only policy

The prompt text and parser/formatter bodies are mechanically preserved from the Run242 preimage; only dependency binding moved to explicit keyword injection where needed.

## Falsification

Pre-PR migration validation:

- guarded dry-run: PASS
- guarded write: PASS
- compile: PASS
- Run243 module tests: **7/7**
- Run243 integration/live-binding tests: **6/6**
- dedicated total: **13/13**
- adjacent article-quality regressions: PASS
- Run134 monthly Decision Brief regression: PASS
- Revenue Product Phase2: **37/37**
- migration idempotency: PASS
- `git diff --check`: PASS

Permanent CI owns the Run243 module/integration tests after this migration.
