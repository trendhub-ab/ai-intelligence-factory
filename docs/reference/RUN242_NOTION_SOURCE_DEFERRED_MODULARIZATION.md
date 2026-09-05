# Run242 — Notion Payload / Source Document / Deferred Queue Modularization

## Purpose

Run242 continues the strangler-style slimming of `pipeline.py` without changing Production quality, quota, persistence, publication, or product behavior. It extracts three deterministic domains that do not need provider SDKs or direct persistence ownership.

## Canonical ownership

### `notion_payloads.py`

Owns pure payload shaping only:

- safe rich-text chunking
- Notion date property shaping
- Deep Dive property payload construction
- manuscript code-block payload construction
- full page payload construction
- Stock metadata property construction

It does **not** call the Notion API, read credentials, write files, or select canonical databases. `pipeline.py` continues to own live property/status names, `_notion_parent()`, and all Notion network writes.

### `source_document_parsing.py`

Owns deterministic parsing of already-available source material:

- GitHub repository URL identity helpers
- GitHub global-navigation rejection
- explicit Markdown evidence-link extraction
- effective evidence-source classification
- redundant arXiv DOI rejection
- HTML readable-text parsing
- research-link parsing
- low-value arXiv navigation rejection
- evidence compression
- regex-based evidence metadata shaping

It performs **no HTTP requests**. Acquisition, redirect validation, SSRF protection, PDF retrieval, arXiv/GitHub API access, and all network behavior remain in `pipeline.py`.

### `deferred_queue_policy.py`

Owns pure Deferred Deep Dive queue policy:

- shelf-life TTL mapping
- queue identity
- JSON-safe serialization
- expiry filtering
- persisted payload shaping
- merge/ranking/capacity split
- pop/slice behavior

Filesystem/GitHub persistence and the Notion Pending Retry fail-safe remain in `pipeline.py`.

## Physical slimming

- Run241 preimage: **11,497 lines**
- Run242 postimage: **11,172 lines**
- Net reduction: **325 lines**

The line reduction is a maintainability result, not a claim that Production E2E latency improves by the same amount. Runtime optimization remains evidence-driven through `run231_performance_telemetry.py`.

## Protected contracts

Run242 does not change:

- Gemini model/fallback order or model call sites
- RPD/RPM/TPM limits, persistent counters, pacing, retry budgets, or Pending Retry limits
- Fact / Evidence / Decision / Publication / Human Appeal thresholds or blocking semantics
- Screening thresholds, Stock eligibility, Deep Dive request budget, or Decision Score formula
- Notion schema, canonical database destination, or subscriber product contract
- public note release policy
- Daily PAUSED state

Notion writes, source-network acquisition, quality-gate execution, Product Review, and article backlog processing remain outside the extracted modules.

## Falsification contract

Run242 uses `run242_notional_source_deferred_migration.py` with an exact **11,497-line Run241 preimage** guard and required AST/source markers. Unexpected source shape fails closed before writing.

Dedicated tests cover:

- provider/network/persistence-free module surfaces
- Notion payload/status/date/chunk contracts
- conservative GitHub/arXiv/source-link parsing
- evidence metadata word-boundary behavior
- Deferred TTL/identity/expiry/ranking/overflow behavior
- pipeline live-binding compatibility
- physical ownership transfer
- Deferred persistence-failure fallback to Notion Pending Retry

Existing Revenue Product Phase2, Context-First, Cross DB, full pytest, and synthetic Production-isolation regressions remain required before merge.
