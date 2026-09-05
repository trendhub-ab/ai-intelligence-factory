# Run240 — Editorial Naturalness Modularization

## Purpose

Continue the pipeline strangler refactor without changing article quality behavior, Gemini usage, or publication policy.

Run240 extracts the deterministic editorial-naturalness diagnostics that were still physically embedded in `pipeline.py` into `editorial_naturalness.py`.

## Physical change

- `pipeline.py`: **12,726 → 12,461 lines**
- Net reduction: **265 lines**
- New canonical module: `editorial_naturalness.py`
- `pipeline.py` retains thin live-binding wrappers only.

Canonical ownership moved for:

- article claim-role counting
- fabricated personal-experience detection
- AI-style composite diagnostics
- sentence shingling / Jaccard support
- human-editorial depth diagnostics
- style-sequence fingerprints
- rhetorical-template phrase detection
- cross-article naturalness fingerprints

## Live-binding contract

The extracted module must not freeze Production runtime state.

`pipeline.py` continues to supply at call time:

- `ARTICLE_DISPLAY_VARIANTS`
- `_RUN_ARTICLE_STYLE_MEMORY`
- `_article_opening_excerpt`

This preserves runtime monkeypatch/testing behavior and the existing cross-article memory semantics.

## Explicit non-changes

Run240 does **not** change:

- Gemini model pool, fallback order or SDK call path
- RPD/RPM/TPM limits, persistent counters, pacing or retry budgets
- Fact / Evidence / Decision / Publication / Human Appeal thresholds
- any regex, score threshold or `high` boundary in the extracted diagnostics
- Reader Experience `soft_only=True`
- Screening, Stock eligibility, Deep Dive ranking or request budget
- Notion schema or canonical destinations
- Daily PAUSED
- public note release human-only

## Falsification

Required before merge:

- fail-closed mechanical migration
- `py_compile` / `compileall`
- provider/persistence/environment-free module ownership checks
- live wrapper parity for display variants, peer memory and opening helper
- existing Human Voice / Reader Delight / Narrative / Human Appeal regressions
- full pytest
- Synthetic smoke with `critical_failures=0`
- `production_write_isolation=true`
- Repository-wide Falsification Guard
- Integration Reconciliation CI
- Cross DB Contract Guard
- Notion Access Policy Guard
- Documentation Freshness Guard

## Rollback

Rollback is the Run240 squash commit only. No schema/data migration is performed, so rollback does not require Notion or operational-state repair.
