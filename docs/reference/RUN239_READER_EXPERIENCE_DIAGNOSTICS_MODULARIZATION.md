# Run239 — Reader Experience Diagnostics Modularization

## Purpose

Run239 continues the strangler-style slimming of `pipeline.py` without changing article quality behavior. The 390-line `_reader_experience_signals()` implementation is mechanically extracted into the provider-free `reader_experience_signals.py` module.

## Physical result

- `pipeline.py`: **13,112 -> 12,726 lines** (**-386 lines**)
- canonical extracted module: `reader_experience_signals.py` (**397 lines**)
- the heavy reader-experience algorithm is physically absent from `pipeline.py`
- `pipeline.py` retains only a thin compatibility wrapper that binds the current live `_article_opening_excerpt` helper

## Canonical ownership

`reader_experience_signals.py` owns the deterministic diagnostics for:

- accessibility and unexplained-jargon observation
- opening non-engineer access
- reader proximity and conversational-overuse observation
- article-specific angle and heading pull
- plain-language / everyday bridge observation
- jargon translation and information-budget observation
- narrative understanding progression
- Reader Delight composite observation
- return pull, scene presence, and explanatory-run observations

The extracted module is stdlib-only and has no Gemini, Notion, GitHub, HTTP, environment, persistence, or credential dependency.

## Exact-behavior migration contract

Run239 does not redesign these diagnostics. The migration copies the historical function body mechanically and changes only two binding surfaces:

1. `_reader_experience_signals(article)` becomes `reader_experience_signals(article, article_opening_excerpt_fn)`.
2. The single call to `_article_opening_excerpt(body, 700)` becomes a call to the supplied `article_opening_excerpt_fn` callback.

The pipeline compatibility wrapper binds the callback at call time:

```python
def _reader_experience_signals(article: str) -> dict:
    return _reader_experience_signals_impl(article, _article_opening_excerpt)
```

This preserves runtime patchability and existing opening-excerpt semantics while removing the heavy algorithm from the orchestration file.

## Protected Production contracts

Run239 must not change:

- any Reader Experience regex, threshold, status label, or composite decision
- the `soft_only=True` contract of reader-experience diagnostics
- Gemini model selection, fallback order, RPD/RPM/TPM, persistent counters, pacing, retry budgets, or request counts
- Fact / Evidence / Decision / Publication / Human Appeal gate thresholds or blocking semantics
- Screening, calibration, Stock eligibility, Deep Dive ranking or request budget
- Notion schema, canonical destinations, subscriber product behavior, or monthly Digest behavior
- Daily workflow PAUSED state
- human-only public note release

Reader-experience diagnostics remain zero-model observations. They do not independently spend Gemini retry budget and may not be used to weaken hard factual/evidence contracts.

## Falsification

Permanent regression ownership includes:

- `tests/test_run239_reader_experience_module.py`
  - stdlib/provider-free ownership
  - no hidden pipeline-global dependency
  - exact thin wrapper and canonical import
  - heavy implementation physically removed from `pipeline.py`
  - soft-only diagnostics contract
- `tests/test_run239_reader_experience_integration.py`
  - exact canonical function identity
  - live wrapper/module output parity on representative articles
  - live opening-excerpt binding
- existing Reader Value / Reader Delight / Narrative Understanding regressions
- full pytest regression
- synthetic production-stack smoke with production-write isolation
- Repository-wide Falsification Guard and Integration Reconciliation CI

## Migration governance

`run239_reader_experience_migration.py` is fail-closed and idempotent after migration. It refuses to operate if the historical ownership surface no longer matches the expected structure.

Temporary analysis/migration workflows used to perform the extraction are not part of the Production baseline and must be retired before merge.
