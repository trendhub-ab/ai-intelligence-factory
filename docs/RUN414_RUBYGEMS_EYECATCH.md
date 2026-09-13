# Run414 — RubyGems one-off Gemini 3.5 eyecatch bridge

## Scope
Operator-approved one-off continuation for Content Intelligence page `3d9479ff-dca9-819a-814c-e4a0aeb3263f` only.

## Contract
- Article body generation/repair remains zero model calls and is not modified.
- Gemini 3.5 (`gemini-3.5-flash`) is used for exactly one bounded public-headline JSON request.
- Gemini 3.8 is intentionally not used and remains reserved.
- The generated headline may not add facts, numbers, outcomes, urgency, scores, or clickbait.
- Image bytes are produced by the existing deterministic `editorial_eyecatch.generate_note_editorial_eyecatch` renderer at 1280x670 with category `SECURITY`.
- Existing `アイキャッチ` is never overwritten.
- The PNG is uploaded to Notion and attached to the exact page's `アイキャッチ` Files property.
- On successful attachment only, dispatch normal Note Ready sync with `create_private_draft=true`.
- Public note publication is forbidden; the operator publishes manually.

## Economics
The intended happy path consumes one Gemini 3.5 request and zero Gemini 3.8 requests. There is no automatic 3.8 fallback, so the last 3.8 request remains available for a genuinely higher-value failure recovery.
