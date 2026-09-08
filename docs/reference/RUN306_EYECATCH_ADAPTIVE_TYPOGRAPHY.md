# Run306 Eyecatch Adaptive Typography

## Purpose

Run306 fixes the visual imbalance observed in real note eyecatches when the main catch copy spans two or three lines. The prior renderer used fixed title top coordinates; in particular the three-line anchor (`226`) was above the two-line anchor (`234`), so dense copy could become top-heavy.

This is a deterministic presentation-only refinement. It does not add a Gemini/model request, alter article facts, change Evidence/Decision gates, mutate note, or publish anything.

## Production contract

Run306 is installed by the existing final eyecatch presentation layer in `run296_editorial_format_v2.py`, after Run183 has established the orange conclusion-emphasis scale.

### Font sizing

- Normal headline maximum: **72 px**.
- This ceiling matches the human-reviewed Netflix GenRec specimen (`Netflix推薦の舞台裏 / LLMネイティブへ / 舵を切った理由`).
- The model-proposed `title_font_size` is no longer the authority for final rendering.
- The renderer starts from 72 px and measures actual glyph widths/heights with Pillow.
- It reduces the size only when needed to fit the existing title width and safe-height constraints.
- Minimum fallback size remains **48 px**.
- Run183 orange emphasis remains 20% larger when geometry allows, with a Run306 ceiling of **86 px**, matching the current reviewed specimen scale.

### Vertical balance

- Two-line and three-line title blocks use a shared visual center at **Y=370** on the 1280×670 canvas.
- The historical two-line (`234`) and three-line (`226`) title-top values are retained only as minimum safe boundaries.
- The actual title-block height is measured first.
- Final title top is calculated as `visual_center_y - block_height / 2`, then clamped to the existing safe region.
- Therefore shorter/two-line copy can sit lower without becoming top-heavy, while three-line copy remains balanced rather than being forced upward.

### Preserved contracts

- Run180 semantic 2–3 line breaking remains authoritative.
- Run296 protected Japanese compounds remain atomic.
- Run182 highlight phrase selection remains unchanged.
- Run183 20% conclusion emphasis remains unchanged apart from the explicit reviewed-size ceiling.
- The right-side network illustration, brand, top tags, footer, category colors, and 1280×670 canvas are unchanged.
- Run296 lower explanatory subheadline remains disabled.
- No new provider/model call is introduced.
- Scheduled Daily remains PAUSED.
- Public note release remains human-only.

## Falsification / regression requirements

Run306 regression tests must prove:

1. The Netflix three-line specimen can use the 72 px normal-title ceiling.
2. Font size is identical for the same text regardless of a smaller/larger model size hint.
3. Longer copy shrinks below the reference ceiling when geometry requires it.
4. Synthetic two-line and three-line blocks share the same Y=370 visual center.
5. A real three-line profile moves down from the former fixed 226 px anchor.
6. No provider-call or note-publication surface is introduced.

## Cost impact

Gemini/model requests added by Run306: **0**.
