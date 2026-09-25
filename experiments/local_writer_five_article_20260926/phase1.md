# Phase 1 — Unmodified v1 baseline

This phase intentionally runs the exact Local Writer from Experiment 1 across five heterogeneous records.

No Writer repair is applied before measurement.

The goal is to expose generalization failures, especially:

- topic-specific glue that accidentally leaks from the first experiment,
- numeric claim handling,
- jargon / reader accessibility,
- cross-article stylistic fingerprinting,
- source-shape differences,
- prior Needs Editorial Review cases.

Results are read from CI logs before any experiment-only repair is introduced.
