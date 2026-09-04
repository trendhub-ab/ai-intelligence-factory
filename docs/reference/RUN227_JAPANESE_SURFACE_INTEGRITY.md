# Run227 — Japanese Surface Integrity

## Purpose

Run226 FULL ONE-SHOT #24 produced two otherwise-Ready manuscripts containing obvious broken Japanese:

- `結果はでした。`
- `AIモデルの計算はに速くなる`

Run227 closes that publication-surface gap without adding a model call or weakening any existing quality contract.

## Production behavior

`run227_japanese_surface_integrity.py` wraps the existing Fact Gate and adds only high-confidence surface checks:

1. Predicate-less topic + copula patterns such as `結果はでした。`.
2. A narrowly scoped `はに` particle collision before comparative/change stems such as `速`, `遅`, `高`, `低`, `大`, `小`, `増`, `減`, `変`.
3. Fenced code and inline code are excluded from scanning.

A match is a fail-closed Fact Gate failure with reason prefix `malformed_japanese_surface:`.

## Repair policy

Run227 does **not** deterministically rewrite the sentence. The missing predicate/adverb cannot be recovered safely without semantic guessing. The existing bounded retry path receives a local instruction to fix only the malformed sentence while preserving Fact/Evidence/Decision.

The repair must not invent:

- facts
- numbers
- people
- causal claims
- source conditions

## Invariants

- zero new Gemini/model call sites
- no Decision Score change
- no Evidence threshold change
- no source URL change
- no deterministic semantic rewrite
- normal Fact / Editorial / Publication / Human Appeal re-evaluation remains mandatory
- Daily remains PAUSED
- public note release remains human-only

## Publication policy

Run227 is part of `PUBLICATION_POLICY_FILES`. A Ready manuscript stamped before Run227 is not current-policy Ready and must be reconciled before it can remain in the note posting queue.

`.github/workflows/note-ready-sync.yml` watches both the Run227 implementation and its regression test so policy changes reconcile the queue immediately on `main`.

## Regression evidence

`tests/test_run227_japanese_surface_integrity.py` contains exact regressions for both Run #24 Production escapes, valid neighboring Japanese, code exclusion, idempotent installation and retry instruction behavior.
