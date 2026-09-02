# Run179 — Eyecatch Font Refinement

## Goal
Improve public note eyecatch readability and visual polish without changing Run178 semantic line-break decisions or article copy.

## Production typography
- Title: Noto Sans JP, weight 900 (Black)
- Subheadline: Noto Sans JP, weight 500 (Medium)
- Latin UI / category / date: Inter, weight 700 (Bold)

## Asset policy
The official Google Fonts variable files are downloaded only for a real production run from the immutable `google/fonts` commit `45b0855d499c093e4d1bd08926fec4e1a582e225`.

They are stored under the runner temporary directory, never under the repository tree, so pipeline self-commit logic cannot accidentally publish font binaries.

If download, font loading, or variation-axis configuration fails, rendering continues with system Noto/Lato/DejaVu fallback fonts.

## Safety contract
- Run178 remains the owner of semantic line-break and bounded-size decisions.
- Run179 changes font resolution only.
- No title/subheadline copy rewrite is introduced.
- Public image contract stays 1280×670 RGB PNG.
- Synthetic Regression never downloads fonts and remains zero Gemini API.
- Daily remains PAUSED.
- ONE-SHOT is not automatically executed by this change.
- note publishing automation is not part of Run179.
