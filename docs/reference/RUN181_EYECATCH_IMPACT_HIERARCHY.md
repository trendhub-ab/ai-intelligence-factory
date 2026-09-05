# Run181 Eyecatch Impact Hierarchy — Current Production Contract

Updated: 2026-09-05

The public note eyecatch keeps the approved deterministic white/network background and right-side illustration. The adopted improvement is a foreground-only, copy-led hierarchy rendered inside the existing Run181/182/183 path.

## Adopted hierarchy

1. Keep `AI Intelligence Factory` brand and the existing top-right category/date tags.
2. Add one compact reader-purpose badge on the upper-left using deterministic topic cues only. `初心者向け` is **not** the generic fallback; it is reserved for explicit beginner/introductory cues.
3. Current badge taxonomy is: `初心者向け`, `比較で理解`, `安全性を確認`, `論文をやさしく`, `実務で判断`, `最新動向を理解`, `仕組みを理解`, `開発で使う`, `データを理解`, `要点を理解`.
4. Each badge owns a fixed vector-style icon drawn only with Pillow primitives. No generated icon, SVG download, external asset, or additional API call is used. The beginner badge uses a deterministic Japanese beginner-mark-inspired green/yellow shield; the other purposes use compare arrows, shield/check, paper, briefcase/check, trend pulse, mechanism nodes, code brackets, database, or checklist symbols.
5. Add one short editorial hook above the title. Hooks are curiosity framing only and may not introduce a factual claim.
6. Render the main eyecatch title larger and lower than the historical Run181 layout. Existing Run180 semantic line breaks remain authoritative when available.
7. Keep Run182/183 exact-substring orange emphasis `#F28C28`; emphasis remains geometry-bounded and falls back toward the normal size rather than overflowing.
8. Render the existing source-bounded subheadline below the main title. When a semantic layout plan is unavailable, derive it through the existing deterministic `editorial_subheadline()` path rather than inventing copy.
9. Add a compact category/date footer on the lower-left.

## Badge classification order

Badge selection is deterministic and intentionally avoids making the publication grid look like every article is a beginner tutorial.

1. comparison cues -> `比較で理解`
2. security/risk cues or `SECURITY` category -> `安全性を確認`
3. research/paper cues or `RESEARCH` category -> `論文をやさしく`
4. explicit beginner/intro cues -> `初心者向け`
5. developer/tool cues or `DEV TOOLS` -> `開発で使う`
6. database/RAG/data cues or `DATA` -> `データを理解`
7. adoption/operation/business cues or `AI BUSINESS` -> `実務で判断`
8. announcement/release/update cues -> `最新動向を理解`
9. mechanism/how/performance cues or model/agent/infra/multimodal/robotics categories -> `仕組みを理解`
10. otherwise -> `要点を理解`

This badge is presentation metadata only. It never changes Fact, Evidence, Decision, article text, score, or publication eligibility.

## Typography contract

Run181 continues to resolve fonts through `editorial_eyecatch`, so Run179 remains authoritative:

- main Japanese title: **Noto Sans JP Black / weight 900**
- Japanese supporting copy / badge: **Noto Sans JP Medium / weight 500** unless title-role sizing selects the title face through the existing Run179 resolver
- Latin UI: **Inter Bold / weight 700**
- existing system Noto/Lato fallback remains unchanged when Google Fonts preparation fails

The badge/icon update does not add direct `ImageFont.truetype()` ownership to Run181.

## Cost and safety invariants

- Additional Gemini/model requests: **0**.
- Image-generation API requests: **0**.
- Icon-generation API requests: **0**.
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
- Badge icon is contained inside the existing upper-left badge band and may not overlap the hook/title.
- Title block is bounded above the subheadline area; subheadline is limited to two lines.

## Regression requirements

Tests must prove:

- `初心者向け` is used for explicit beginner content and is not the generic fallback;
- comparison/security/research/developer/data/practical/news/mechanism variants are deterministic;
- every supported badge has a nonblank fixed vector-style icon;
- Run181 still resolves fonts through the existing Run179-patched `ee._jp_font` / `ee._latin_font` path;
- the Polars-style performance title selects the strong curiosity hook;
- short titles scale larger when geometry permits;
- orange emphasis remains visible;
- the entire approved right-side surface is pixel-identical to the existing background/illustration/tag draw path;
- no `_generate_via_chat`, `call_gemini`, `generateContent`, network download, or image-generation call site is added by the badge/icon helper.
