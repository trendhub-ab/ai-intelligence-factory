# Eyecatch Decision Card Validation — 2026-08-22

## Approved layout
- Canvas: 1280 x 670
- Source-specific background: GitHub / HackerNews / ArXiv / ProductHunt
- Article title is not duplicated inside the image
- Main KPI: `意思決定スコア (Decision Score) X/100`
- Progress bar: length proportional to Decision Score; color follows the approved five-band scale:
  - 0–59: Slate Gray `#64748B`
  - 60–69: Cyan `#22D3EE`
  - 70–79: Blue `#3B82F6`
  - 80–89: Purple `#8B5CF6`
  - 90–100: Gold `#F5B942`
- Red is intentionally reserved for future AVOID / warning semantics
- Lower-left: `技術的破壊力 (Technical Impact) X/25`
- Lower-right: `緊急度 (Urgency) X/20`
- Eyecatch eligibility: Article Ready; no Decision Score minimum threshold

## Data source
The lower two values are extracted from the existing Deep Dive MANAGEMENT DATA `Score Breakdown` only. No additional Gemini request and no recomputation are permitted. Missing or malformed values fail closed to `—`.

## Validation
- Unit tests: 384/384 PASS
- Synthetic Regression Full: 500/500 PASS
- Critical failures: 0
- Production writes: disabled
- Preview rendered with ArXiv background at Decision Score 81, Technical Impact 21/25, Urgency 12/20; progress bar is Purple #8B5CF6
- Existing Notion schema: unchanged
- Additional Gemini API calls: 0
