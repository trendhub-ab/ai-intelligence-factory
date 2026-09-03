# Run222 — note Presentation Integrity

Date: 2026-09-04

## Purpose

The first real private-note E2E draft exposed three presentation defects that were not visible in zero-browser tests:

1. the subscriber CTA appeared before `Sources / Evidence` and the disclaimer;
2. the article H1 duplicated note's own title field;
3. because the safe HTML converter intentionally supported H2-H4, the duplicated H1 could surface as a raw Markdown `#` line in the note body.

Run222 fixes those defects without adding model calls, weakening Evidence, or enabling public release.

## Production contract

### Footer order

Public note manuscripts must end in this trust-first order:

1. article body / conclusion;
2. `Sources / Evidence` and any supplementary Evidence;
3. source-rights / attribution notes;
4. article disclaimer;
5. subscriber CTA (`AI Decision Intelligence`).

The CTA is the final reader action. Evidence and the disclaimer remain part of the article itself and must not appear after the sales/navigation action.

### note editor presentation

The stored Ready manuscript remains the byte-exact object validated by the Publication Contract. Only after that validation succeeds may the note editor presentation layer:

- remove a leading `# <title>` when it duplicates the note title field;
- demote any remaining body H1 to H2 outside fenced code blocks so raw `#` markup is never exposed;
- move a historical pre-Run222 CTA from before Sources/Evidence to the end.

These presentation transforms must not be applied before Publication Contract validation.

### Safety invariants

- zero Gemini/model calls;
- no public-release action;
- no Evidence, Decision, score, source URL, or article fact changes;
- stored current-contract manuscript validation remains fail-closed;
- transform is idempotent when footer order is already correct;
- code fences are not rewritten while demoting body H1 headings.

## Implementation

- `run222_note_presentation_integrity.py`
  - `install_pipeline()` corrects future canonical manuscript footer order.
  - `install_note()` applies editor-only cleanup after current-contract validation.
- `production_pipeline.py` installs Run222 after Run208 and before Run194 Publication Contract stamping.
- `run194_note_persistent_cloud.py` installs the note-side transform after `current_contract.install()`.
- `publication_contract.py` includes Run222 in `PUBLICATION_POLICY_FILES`.
- `.github/workflows/note-ready-sync.yml` reconciles the note Ready queue when Run222 changes.

## Regression coverage

`tests/test_run222_note_presentation_integrity.py` verifies:

- CTA is moved after Sources + disclaimer;
- already-correct footer order is idempotent;
- duplicated leading H1 is removed;
- remaining H1 is demoted outside code fences;
- note transform runs after the existing prepare/current-contract guard;
- pipeline wrapper changes only presentation order, not article body semantics.
