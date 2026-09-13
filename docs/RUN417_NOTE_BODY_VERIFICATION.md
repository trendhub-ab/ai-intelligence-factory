# Run417 — Structural note body insertion verification

## Background
The exact RubyGems Ready article passed publication preflight and reached the real note editor, but draft creation failed closed at body insertion verification. The historical verifier required the first 32 plain-text manuscript characters to appear in the note body. The manuscript begins with a Markdown H1 while note keeps its document title in a separate title field, so a healthy title/body split can fail that prefix-only check.

## Contract
- Zero Gemini/model calls.
- Ignore at most one leading Markdown H1 for body-verification purposes only; title verification remains separate in the existing save/persistence checks.
- Normalize NFKC, whitespace, NBSP and zero-width/BOM differences before comparison.
- Require a meaningful body-length floor plus at least two distributed anchors from the expected visible body.
- A short insertion, a one-anchor partial insertion, unreadable body, or empty expected body remains fail-closed.
- No article-body rewrite, Publication Gate relaxation, note public-release action, X change, or model-budget change.

## Production wiring
`run190_note_persistent_cloud.install()` installs Run417 before the real persistent-Chrome draft mutation. Existing image upload, editor-route, save, reload/persistence and Notion-state checks remain in force.

## Publication boundary
This repair exists only to distinguish a valid note title/body separation from malformed body insertion. It creates private drafts only; public publication remains human-only.
