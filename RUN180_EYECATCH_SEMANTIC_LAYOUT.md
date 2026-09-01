# Run180 — Eyecatch Semantic Layout

## Why

Real-image QA after Run178/179 confirmed that Noto Sans JP Black improved legibility, but the original Run178 runtime still fell back too often. The first visual samples exposed destructive mechanical wrapping such as splitting `エージェント`, `競争`, and `モデル` across lines.

The QA also exposed the runtime causes: schema output may be available through `response.parsed`, Gemini 3.5 Flash needs a bounded thinking configuration for this tiny layout task, and the old 34-character headline pre-truncation can remove meaning before the art-director pass.

## Production contract

- Model: `gemini-3.5-flash`
- Role: typography/layout only; no copy rewrite and no pixel generation
- Maximum provider calls: one per public eyecatch
- Thinking: `minimal`
- Output budget: 1400 tokens
- Headline input: public headline up to 48 characters before safe truncation
- Title: Noto Sans JP Black, 42–76 px, 1–3 lines
- Subtitle: Noto Sans JP Medium, 22–28 px, 1–2 lines
- Latin UI: Inter Bold
- Strict validation: exact text partition, kinsoku, width, line count, orphan prevention
- Failure mode: deterministic PIL renderer; no second Gemini call and no model fallback
- Synthetic Regression: zero API

## Visual QA result

Three deliberately difficult Japanese titles were tested with the final configuration. All three returned schema plans, all three passed deterministic validation, and all three rendered without mid-word/mid-morpheme splits. The long technical title remained complete and was arranged across three semantic lines instead of being truncated and mechanically wrapped.

Daily remains PAUSED. Run180 does not implement note auto-publishing; publishing automation is a later phase after the eyecatch contract is stable.
