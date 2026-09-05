# Run181 Eyecatch Impact Hierarchy — Current Production Contract

Updated: 2026-09-05

The public note eyecatch keeps the approved deterministic white/network background and right-side illustration. The adopted improvement is a foreground-only, copy-led hierarchy rendered inside the existing Run181/182/183 path.

## Adopted hierarchy

1. Keep `AI Intelligence Factory` brand and the existing top-right category/date tags.
2. Add one compact reader-purpose badge on the upper-left (`初心者向け`, `比較で理解`, `論文をやさしく`, `実務で判断`, or `安全性を確認`) using deterministic topic cues only.
3. Add one short editorial hook above the title. Hooks are curiosity framing only and may not introduce a factual claim.
4. Render the main eyecatch title larger and lower than the historical Run181 layout. Existing Run180 semantic line breaks remain authoritative when available.
5. Keep Run182/183 exact-substring orange emphasis `#F28C28`; emphasis remains geometry-bounded and falls back toward the normal size rather than overflowing.
6. Render the existing source-bounded subheadline below the main title. When a semantic layout plan is unavailable, derive it through the existing deterministic `editorial_subheadline()` path rather than inventing copy.
7. Add a compact category/date footer on the lower-left.

## Cost and safety invariants

- Additional Gemini/model requests: **0**.
- Image-generation API requests: **0**.
- Existing Run180 layout request count: unchanged.
- Background/right-side illustration: unchanged deterministic `editorial_eyecatch` drawing functions.
- Fact / Evidence / Decision / score / source URL: unchanged.
- Public note release: human-only.
- Run248 fallback continues to call the same Run181 renderer, so semantic-provider failure must still land on the current impact hierarchy rather than the pre-Run181 fallback typography.

## Geometry contract

- Canvas: `1280x670`.
- Foreground hierarchy remains on the left and must not alter pixels at `x >= 820`.
- Main title text area remains bounded to `760px` width.
- Impact title may scale up to `88px`; Run183 orange emphasis may scale up to `104px` only when width and vertical safety constraints pass.
- Title block is bounded above the subheadline area; subheadline is limited to two lines.

## Regression requirements

Tests must prove:

- the Polars-style performance title selects the strong curiosity hook;
- comparison/security/research badge or hook variants are deterministic;
- short titles scale larger when geometry permits;
- orange emphasis remains visible;
- the entire approved right-side surface is pixel-identical to the existing background/illustration/tag draw path;
- no `_generate_via_chat`, `call_gemini`, or `generateContent` call site is added by Run181.
