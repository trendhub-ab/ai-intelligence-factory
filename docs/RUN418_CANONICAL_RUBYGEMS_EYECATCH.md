# Run418 — Canonical RubyGems Eyecatch Restoration

## Background

The one-off Run416 recovery attached an eyecatch by calling the raw `editorial_eyecatch` renderer through Run414. That bypassed the current Production eyecatch runtime. The resulting image was not a degraded version of the approved design; it was a different base template: wrong Japanese font fallback, wrong copy geometry, raw SECURITY accent treatment, and missing current editorial hierarchy layers.

Run418 repairs that routing error. It does not hand-tune the screenshot or introduce a new design.

## Canonical visual contract

The exact RubyGems article must use the same installed Production eyecatch stack as normal publication:

- Run179 — pinned Noto Sans JP / Inter font policy
- Run180 — one bounded Gemini 3.5 semantic title/layout direction
- Run181 — visual mass and copy placement
- Run182 — restrained orange conclusion emphasis
- Run183 — emphasis scale
- Run296 / Run306 — current reader-approved editorial format and adaptive typography

The raw `editorial_eyecatch.generate_note_editorial_eyecatch()` entrypoint is not an acceptable one-off publication path.

## Model budget

Run418 permits exactly one logical model request, and only for the existing Run180 `eyecatch_layout` request using `gemini-3.5-flash`. Gemini 3.8 is not selected. No model call is used for the article body or private-draft refresh.

The workflow uses the repository-wide `ai-intelligence-gemini-budget` concurrency group and supplies the same `GH_PAT` authorization required by the persistent Gemini daily-usage counter. Missing quota-ledger authorization fails closed before the provider call; it must never bypass or disable the shared counter.

If the semantic layout plan is missing or invalid, Run418 fails closed. It must not fall back to the raw white base template.

## Exact target and mutation boundary

Run418 is pinned to Content Intelligence page `3d9479ff-dca9-819a-814c-e4a0aeb3263f` and the exact RubyGems source/note titles. The Notion replacement phase requires the current single eyecatch to be the known broken Run416 asset `run414-rubygems.png` before replacing it with `run418-rubygems-canonical.png`.

The article body, Decision data, source evidence and article status are not modified.

## Existing note draft

A verified private note draft already exists. Run418 therefore must not create a second draft. It discovers the exact existing `/notes/<id>/edit` route from the persistent Chrome history, requires a unique title match, replaces only the existing header image using the previously proven Run298 safe hover/remove/upload path, saves the same draft, then verifies:

- the edit-route identity is unchanged;
- the title is unchanged;
- the normalized visible body is byte-for-byte equivalent before/after the header repair;
- the header media fingerprint changed and persisted;
- Note Ready remains `Ready / 投稿準備中` with no public-post evidence.

Public release remains manual and outside Run418.

## Regression policy

`tests/test_run418_rubygems_canonical_eyecatch.py` locks the exact target, Production-layer dependency, one-model 3.5-only direction contract, no raw renderer fallback, header-only existing-draft mutation, no duplicate draft and no public-release surface.
