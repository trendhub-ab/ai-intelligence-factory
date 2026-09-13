# Run423 — Latin Identifier Line Integrity

## Background

Run422 correctly restored the latest AIIF eyecatch layout contract: the copy area is fixed while the main copy may occupy two or three lines according to measured width. The real RubyGems render exposed one remaining typography defect: the renderer produced `Ru` / `byGems` across two lines.

That output satisfies the numeric two-line contract but violates the higher-level editorial rule that product names and technical identifiers must remain intact.

## Contract

Run423 keeps the Run422 layout contract and adds one stronger boundary rule:

- main copy remains exactly 2 or 3 lines;
- copy position and right-side illustration area remain unchanged;
- protected Latin identifiers such as `OpenAI`, `RubyGems`, `MCP`, `RAG`, model names and similar alphanumeric tokens must be wholly contained in one line;
- a Latin identifier split across two lines is a hard layout failure;
- concatenated title lines must still equal the exact approved eyecatch title;
- no new fact, urgency or claim may be added merely to improve wrapping.

For the exact approved RubyGems repair, the semantic partition is pre-seeded as:

- `OpenAIエージェントと`
- `RubyGems、権限管理の境界線`

Run419 remains responsible for font-size fitting and full Run180 geometry validation. If this semantic partition cannot fit the canonical area within Production bounds, the run stops rather than splitting `RubyGems` or falling back to another template.

## Cost and mutation boundary

- Gemini calls: 0
- image-generation API calls: 0
- article body changes: 0
- exact Notion page only
- existing private note draft updated in place, header only
- no duplicate draft
- no public publication

## Regression

`tests/test_run422_pinned_canonical_copy.py` now verifies:

- valid 2-line and 3-line partitions;
- 1-line and 4-line rejection;
- explicit rejection of the observed `Ru` / `byGems` split;
- complete preservation of `OpenAI` and `RubyGems` on individual lines;
- zero-model and no-raw-renderer paths remain intact.
