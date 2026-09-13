# Run422 — Pinned Source-bounded Canonical Copy

## Background

Run421 removed Gemini from the one-off RubyGems eyecatch repair, but the generic 48-character `editorial_hook_from_title` still failed the real Run180/Noto validation contract. No Notion or note mutation occurred.

The generic hook is useful for broad fallback behavior, but this exact already-approved article does not need another heuristic compression stage. The repair should minimize cost and uncertainty while restoring the current Production visual design.

## Exact copy contract

Run422 pins the public eyecatch copy for this exact RubyGems article to:

- title: `OpenAIエージェントとRubyGems、権限管理の境界線`
- subheadline: `AIエージェントの権限設計を考える`
- restrained emphasis: `権限管理の境界線`

The title is a direct compression of the existing note title. It preserves the protected Latin identifiers required by Run180 (`AI`, `OpenAI`, `RubyGems`) and adds no new fact, number, causal claim or urgency. The subheadline restates the existing permissions-design subject without adding a new factual assertion.

## Canonical layout contract

The latest AIIF reference fixes the copy area and visual hierarchy, not a fixed line count. The main copy must remain in the canonical left-side area while the right-side illustration area stays protected.

The Production layout helper measures the rendered copy width. If the copy fits the canonical area in two lines, it remains two lines; if it needs more space, it may expand to three lines. Run422 explicitly refuses a one-line or four-plus-line result. Semantic phrase boundaries, kinsoku rules, font-size bounds, navy base typography and orange emphasis remain authoritative.

Therefore the canonical contract is:

- copy position/area: fixed
- main-copy lines: exactly 2 or 3, chosen from measured copy length/width
- no forced two-line layout
- no fourth line
- no truncation solely to preserve a fixed line count
- right-side illustration area must not be invaded

## Validation and rendering

The pinned title must first pass `Run180._validate_eyecatch_title` against the original note title. Typography is then rebuilt with the Run419 deterministic repair helper and the final plan must pass the full Run180 geometry contract. Run422 adds an explicit post-validation assertion that `title_lines` contains exactly two or three non-empty lines.

Rendering uses the installed Production validated-plan renderer. Run179/181/182/183/296 therefore remain authoritative for Noto Sans JP / Inter, copy position, navy typography, orange emphasis, brand treatment, background and right-side illustration. The raw/base renderer is never used.

## Cost and mutation boundary

- Gemini calls: 0
- image-generation API calls: 0
- retries: 0
- exact Notion page and known broken current asset are still required before replacement
- existing private note draft is updated in place, header only
- route, title and visible body equality checks remain required
- no duplicate draft
- no public publication

## Regression policy

`tests/test_run422_pinned_canonical_copy.py` locks the required source identifiers, bounded copy length, explicit 2–3-line acceptance, 1-line/4-line rejection, zero-model/no-raw-renderer path, exact-target mutation boundary and no-publication contract.
