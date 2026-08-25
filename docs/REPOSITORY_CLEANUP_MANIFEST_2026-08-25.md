# Repository Cleanup Manifest — 2026-08-25

Baseline: Run127. No production code behavior was intentionally changed.

## KEEP (production / operational)
- Python production modules and scripts
- `tests/`, `.github/workflows/`, `assets/`
- canonical specification and current Run127 documents
- operational state: `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/`
- published assets: `eyecatch_images/`
- required setup docs at repository root

## ARCHIVE
- Run97–Run126 validation/setup/source-requirement documents
- historical mutation logs
- old eyecatch preview/validation files
- one-off release/calibration/failure-injection validation documents

Moved to `docs/archive/`.

## REFERENCE
- Decision Intelligence architecture/business design documents moved to `docs/reference/`.

## ARTIFACT ONLY / REMOVED FROM CLEAN SOURCE TREE
- `.git/` (repository metadata; not source content)
- `.pytest_cache/`, `__pycache__/`
- `article_audit/` local output
- `regression_suite/fixtures/` generated synthetic fixtures
- `regression_suite_runs/` generated reports
- `SHA256SUMS.txt` release-package checksum manifest

## Filename normalization
Three mojibake filenames from the uploaded ZIP were normalized to their canonical UTF-8 Japanese names. Their file contents were byte-identical to the Git index versions.
