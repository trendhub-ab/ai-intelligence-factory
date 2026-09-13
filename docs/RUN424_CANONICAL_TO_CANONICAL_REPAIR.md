# Run424 — Canonical-to-Canonical Eyecatch Repair

## Background

Run423 fixed the observed `Ru` / `byGems` line split, but the live RubyGems Notion page had already been updated by Run422. The current asset name is therefore `run418-rubygems-canonical.png`, not the older Run416 filename. The original Run418 replacement guard correctly refused to overwrite that current canonical asset.

## Exact replacement contract

Run424 keeps the same exact page, title, Ready state and one-file requirement, but changes the allowed precondition from the obsolete broken filename to the currently installed canonical filename.

The replacement is allowed only when all of the following remain true:

- page ID is the known RubyGems page;
- source title and note title exactly match;
- Article Status remains `Ready`;
- exactly one eyecatch file exists;
- that file is exactly `run418-rubygems-canonical.png`;
- the new render preserves the Run423 two-to-three-line and Latin-identifier integrity contract.

Any different page, title, state, file count or filename remains Fail-Closed.

## Cost and mutation boundary

- Gemini calls: 0
- image-generation API calls: 0
- article body changes: 0
- existing private note draft only
- header-only update
- no duplicate draft
- no public publication

## Regression

The Run422/423 regression suite now asserts that the live repair path uses `require_fixed=True` and does not reopen the old `require_broken=True` path.