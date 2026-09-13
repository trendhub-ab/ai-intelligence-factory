# Run421 — Zero-model Canonical RubyGems Eyecatch

## Background

After Run420 fixed premature GitHub Actions cancellation, the real Run418/419 path reached Gemini 3.5 twice. Both requests returned HTTP 200, but both returned plans that failed Run180 semantic/layout validation. No Notion or note mutation occurred.

Repeated model calls are therefore not justified for this one already-approved article. The publication problem is visual routing: the Run416 asset used the raw base renderer and therefore had the wrong copy position, color hierarchy, font/brand treatment and layout.

## Contract

Run421 spends zero model requests. It derives the eyecatch copy from the already-existing deterministic `editorial_hook_from_title(EXPECTED_NOTE_TITLE, max_chars=48)` helper. This copy is source-bounded, introduces no new fact, and must still pass the existing Run180 semantic-title validator.

Typography is rebuilt deterministically using the Run419 repair helper and revalidated through Run180. Rendering then uses the installed Production validated-plan renderer, so Run181/182/183/296 remain authoritative for copy placement, navy typography, orange emphasis, brand treatment, background and right-side illustration. Run179 remains authoritative for Noto Sans JP / Inter.

The exact RubyGems target, known broken current asset requirement, Notion postcondition and existing private-draft header-only update are inherited from Run418.

## Cost and API policy

- Gemini requests: 0
- Google generation API requests: 0
- no image-generation API
- no retry budget
- Notion is used only after a valid 1280x670 canonical PNG is rendered locally.

## Publication boundary

Run421 does not create a second note draft and does not publish. The existing private draft is updated in place only after the Notion asset is replaced. Route, title and body equivalence checks remain required. Public publication remains manual.

## Regression policy

`tests/test_run421_zero_model_canonical_layout.py` proves that copy remains source-bounded, OpenAI/RubyGems identity is preserved, typography is exact-partitioned, the render path contains no model call and no raw renderer, the exact broken asset is required, and no public-release surface is present.
