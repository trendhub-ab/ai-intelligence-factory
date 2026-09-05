# Run231 — Pipeline Modularization / Performance Observability

Status: **Production refactor contract**  
Baseline date: 2026-09-05  
Source of Truth: `main` + `production_pipeline.py` + `runtime_layers.py` + Run231/Run235 regression tests

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

### Stage 2B / Run234 — physical removal and reconciliation

After Stage 2A parity was proven, the duplicate legacy/internal renderer implementation was surgically removed from `pipeline.py` by AST-validated migration and the final reconciliation was merged to `main` as squash commit `b8746ae2bb33f4237edd5b32e298936a30633750`.

- The heavy renderer implementation and six geometry/background helper definitions remain physically removed from `pipeline.py`.
- A thin `generate_eyecatch_image` compatibility def remains because Run99/Run105/Run150/Run160 intentionally inspect the `pipeline.py`/callable source.
- The legacy module's exact absence no longer prevents the live publication path from importing; nested dependency errors, syntax errors, and implementation failures remain fail-closed.
- `production_pipeline.py` no longer redundantly reimports/reinstalls the obsolete legacy renderer.
- Preserved `_sanitize_filename`, `upload_eyecatch_to_github`, and the live `generate_note_editorial_eyecatch` import.
- `pipeline.py` changed from **13,649 lines to 13,390 lines**, a net reduction of **259 lines** for this surface while retaining the thin source-compatibility shim.
- The temporary Stage2 compatibility workflow was read-only during reconciliation and is retired in Run235 after successful merge.
- Final pre-merge validation reached **1450 pytest passes**, Synthetic Production **30/30**, critical failures **0**, and production write isolation **true**.

## Stage 3A / Run235 — pure source normalization strangler

The next extraction target is the source-normalization / multilingual-display surface because it is deterministic, provider-free, persistence-free, and shared by all source ingestion paths.

Canonical extracted module: `source_normalization.py`

The Stage3A surface contains only:

- `_detect_title_language`
- `_japanese_product_descriptor`
- `_multilingual_display_name`
- `_notion_display_name`
- `_source_summary_with_original`
- `normalize_item`

Safety design:

1. Historical definitions remain temporarily in `pipeline.py` during Stage3A. This is intentional strangler parity, not a second Production path.
2. `production_pipeline.py` installs `source_normalization` onto the imported `pipeline` namespace **before** `install_runtime_layers(pipeline)`.
3. Historical runtime-layer order remains unchanged; all later wrappers see the extracted canonical normalization functions.
4. The extracted module imports only standard-library text utilities and must not contain provider, network, Gemini, Notion, quota, Fact, Evidence, Decision, or persistence logic.
5. Dedicated Run235 regression compares the extracted and historical implementations independently before installation across Japanese, English, Chinese, Korean, Cyrillic, undefined-language, descriptor, summary, and full normalized-item cases.
6. The existing multilingual-title regression remains an independent downstream persistence compatibility check.
7. Physical deletion of the duplicate block from `pipeline.py` is deferred to a later Stage3B only after Stage3A parity and full Production regression are proven.

Run235 also retires `.github/workflows/run231-stage2-surgical-migration.yml`, because its Stage2 migration role ended when Run234 merged. The permanent Repository-wide Falsification Guard and required `zero-api-regression` now own the continuing modularization safety contract.

## Performance policy

Modularization and runtime optimization are separate concerns.

A smaller file does not justify removing useful gates or requests. Runtime optimization must follow measured Run231 telemetry. Candidate optimizations may include avoiding duplicate I/O, avoiding unchanged Notion writes, per-run Evidence reuse, safe source-fetch concurrency, and CI dependency caching, but only when measurement identifies them as material.

Stage3A is a structural extraction. It does **not** claim a Production runtime improvement merely because logic moved into a smaller module.

## Merge gate

No Run231/Run235 structural change is eligible for `main` unless all relevant checks are green, including the full unittest/full pytest suite and Synthetic Production. Destructive deletion of a validated Production surface requires prior parity proof; the Stage3A duplicate normalization block therefore remains in `pipeline.py` until a later explicitly validated Stage3B.
