# Run178 Eyecatch Editorial Layout Optimizer

## Purpose

Improve the visual quality of the public note eyecatch without handing article copy or image rendering to a model. The approved 1280x670 Editorial Eyecatch remains the visual source of truth.

## Production flow

1. `editorial_hook_from_title` and `editorial_subheadline` create the already-approved public copy.
2. Gemini `gemini-3.5-flash` receives only those two display strings plus typography constraints.
3. The model may choose only line partitions, bounded font sizes, and title line gap.
4. Deterministic validation rejects copy rewrites, excess lines, Japanese kinsoku violations, one-character orphan lines, and width overflow.
5. PIL renders the final image using the existing brand/category/date/network illustration.
6. On provider failure, malformed JSON, invalid layout, or render failure, the existing Run150/160 deterministic Editorial Eyecatch renderer is used immediately.

## Safety contract

- No model may add, delete, rewrite, summarize, or factualize eyecatch text.
- `gemini-3.5-flash` is a layout director only; it does not generate image pixels.
- One layout request at most per public eyecatch attempt. There is no layout retry and no model fallback.
- Layout requests use `request_kind=eyecatch_layout` and `count_as_deep_dive=false` while still passing through the existing local and persistent Gemini quota guards.
- Synthetic Regression skips the provider entirely and remains zero API.
- The existing public image size remains 1280x670 RGB.
- The legacy Decision Score card is not restored as a public fallback.
- Daily remains PAUSED. Run178 adds no note auto-publish behavior.

## Configuration

- `ENABLE_EYECATCH_LAYOUT_OPTIMIZER` (default `true`)
- `EYECATCH_LAYOUT_MODEL` (default `gemini-3.5-flash`)
- `EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS` (default `700`)

The existing `GEMINI_35_FLASH_DAILY_BUDGET` and total Gemini request budget continue to be the hard quota controls. If quota is unavailable, eyecatch generation still succeeds through the deterministic renderer.

## Next phase

After Run178 is production-stable, note publishing automation can consume the same finalized eyecatch image. Publication itself remains a separate change so typography quality and publishing automation can be falsified independently.
