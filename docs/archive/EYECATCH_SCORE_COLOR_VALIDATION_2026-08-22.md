# Eyecatch Decision Score Color Validation — 2026-08-22

## Approved five-band scale
The progress-bar length remains proportional to Decision Score. Its foreground color is selected only from the Decision Score band:

- 0–59: Slate Gray `#64748B`
- 60–69: Cyan `#22D3EE`
- 70–79: Blue `#3B82F6`
- 80–89: Purple `#8B5CF6`
- 90–100: Gold `#F5B942`

Red is intentionally not used for Decision Score; it is reserved for future AVOID / warning semantics. The color communicates score intensity only and MUST NOT be interpreted as Adoption Status.

## Preserved Eyecatch contract
- 1280 x 670
- Source-specific background
- Article title is not duplicated inside the image
- Main KPI: `意思決定スコア (Decision Score) X/100`
- Lower-left: `技術的破壊力 (Technical Impact) X/25`
- Lower-right: `緊急度 (Urgency) X/20`
- Eligibility: Article Ready; no Decision Score minimum threshold
- Additional Gemini API calls: 0

## Boundary regression
Explicit cases cover 0, 59, 60, 69, 70, 79, 80, 89, 90 and 100.

## Validation result
- Unit tests: 384/384 PASS
- Synthetic Regression Full: 500/500 PASS
- Critical failures: 0
- Production writes: disabled
- Python compile: PASS
- Workflow YAML: 5/5 PASS
- ArXiv preview 81/100 renders Purple `#8B5CF6`
