# Run415 — Gemini multi-part eyecatch response parser

## Background
Run414 reached Gemini 3.5 successfully with HTTP 200, but the one-off eyecatch bridge read only `content.parts[0].text`. The real response contained no parseable JSON in that first part, so the workflow failed closed before rendering or Notion upload.

## Change
- Keep the exact RubyGems page, model, prompt, one-request budget and shared Gemini concurrency lock unchanged.
- Read all non-empty textual Gemini content parts.
- Accept only a JSON object containing a non-empty `headline` field; fenced JSON is normalized before parsing.
- No automatic Gemini 3.8 fallback.
- Invalid or missing JSON still fails closed.
- Article body, facts, Decision, Publication Gate and X logic are untouched.

## Quota policy
The first Run414 attempt consumed one Gemini 3.5 request and zero Gemini 3.8 requests. The corrected retry is intended to consume one additional Gemini 3.5 request. Gemini 3.8 remains reserved.

## Publication boundary
Successful eyecatch attachment dispatches the existing Note Ready Sync with private-draft fan-out only. Public note publication remains manual.
