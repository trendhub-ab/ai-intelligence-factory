# Run231 — Pipeline Modularization / Performance Observability

Status: **Production refactor contract**  
Baseline date: 2026-09-05  
Source of Truth: `main` + `production_pipeline.py` + `runtime_layers.py` + Run231 regression tests

## Purpose

Run231 reduces structural risk in the AI Intelligence Factory without trading away article quality, Evidence integrity, product value, or free-tier safety.

The goal is **not** line-count reduction by itself. The goal is to reduce change blast radius, wrapper-order ambiguity, debugging cost, and eventually measured runtime while preserving current behavior.

## Non-negotiable invariants

Run231 must not weaken or bypass any of the following:

- Fact / Evidence / Decision consistency
- primary-source and Evidence authority rules
- Publication Readiness / Human Appeal / Reader Value gates
- Retry / Rescue loss limits and fail-closed behavior
- Gemini model pools, request budgets, persistent RPD accounting, RPM pacing, or timeout reservation rules
- Notion save thresholds, persistence ordering, Pending Retry recovery, or member-product state
- note public-release human-only contract
- Decision Score / Commercial Value separation
- current `generate_note_editorial_eyecatch` publication renderer

Structural changes must add **zero Gemini/model calls** unless a later Run explicitly changes product policy and passes the full publication-policy reconciliation process.

## Stage 1 — Runtime orchestration separation

Stage 1 moved the historical production runtime stack from the production entrypoint into `runtime_layers.py` while retaining the exact validated install order.

- `runtime_layers.py` is the canonical runtime-layer order.
- `production_pipeline.py` is a small orchestration entrypoint.
- legacy callers of `production_pipeline.install_runtime_layers` remain compatible with the canonical implementation.
- `run231_performance_telemetry.py` is observational and fail-open; telemetry failure cannot convert a production success into failure or mask the original production exception.
- telemetry is installed only after runtime layers, runtime-state preflight and font preparation.
- Stage 1 changed no `pipeline.py` quality logic.

Required regression at Stage 1 completion:

- full unittest regression green
- Synthetic Production smoke green
- Repository-wide Falsification green
- Notion Access Policy green
- article-quality reconciliation green
- adjacent product/context regression green

## Stage 2 — Strangler modularization of `pipeline.py`

Stage 2 moves responsibilities out of the monolith in **two phases per surface**:

1. Introduce an isolated module and install it over the historical compatibility surface while leaving the old implementation in `pipeline.py` intact.
2. Only after full zero-API regression proves compatibility may the duplicate historical block be physically removed.

This prevents a hidden import/call dependency from being discovered only after destructive deletion.

### Stage 2A — legacy/internal eyecatch renderer

The first extraction target is the legacy/internal Decision Score card renderer because the current publication renderer is already a separate `editorial_eyecatch` surface.

- New isolated module: `legacy_eyecatch_renderer.py`
- It may use Pillow and local filesystem reads/writes only.
- It must not import/call Gemini, Notion, GitHub API, `requests`, or `pipeline`.
- Production installs it only over legacy/internal symbols such as `generate_eyecatch_image` and its geometry helpers.
- `generate_note_editorial_eyecatch` must remain the exact same callable across the compatibility install.
- Run178–Run183 editorial eyecatch refinement layers continue to operate on the live editorial renderer; they are not replaced by this module.
- Stage 2A parity regression was green before duplicate-code deletion.

### Stage 2B — physical removal after parity proof

After Stage 2A parity was proven, the duplicate legacy/internal renderer implementation was surgically removed from `pipeline.py` by AST-validated migration.

- Removed only seven legacy/internal renderer definitions and their immediately adjacent blank lines.
- Preserved `_sanitize_filename`, `upload_eyecatch_to_github`, and the live `generate_note_editorial_eyecatch` import.
- `pipeline.py` changed from **13,649 lines to 13,353 lines**, a net reduction of **296 lines** for this surface.
- The deletion commit is `2dd1c2b255bbe00d054141ea958da62f29580e24` on the Stage 2 branch.
- The pre-Stage2 main remains preserved on `backup/pre-run231-stage2-2026-09-05`.
- Stage 2B is **not merge-eligible** until the post-deletion full unittest regression, Synthetic Production, Repository-wide Falsification, Notion Access Policy, article-quality reconciliation, and adjacent product/context checks are all green on a normal user-origin PR head.

## Performance policy

Modularization and runtime optimization are separate concerns.

A smaller file does not justify removing useful gates or requests. Runtime optimization must follow measured Run231 telemetry. Candidate optimizations may include avoiding duplicate I/O, avoiding unchanged Notion writes, per-run Evidence reuse, safe source-fetch concurrency, and CI dependency caching, but only when measurement identifies them as material.

## Merge gate

No Run231 structural change is eligible for `main` unless all relevant checks are green, including the full unittest suite and Synthetic Production. A backup branch must exist before destructive deletion/refactoring of a validated production surface.
