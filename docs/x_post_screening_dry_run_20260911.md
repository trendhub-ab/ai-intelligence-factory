# X saved candidate post-screening dry-run — 2026-09-11

## Purpose

Verify the routing immediately after a real saved-X screening result without consuming any additional provider/model quota and without writing to Factory/Notion.

## Input

Defense Factory saved screening observations from 2026-09-11:

- Decision score: 88 in both successful observations
- Commercial score: 90 in both
- Portfolio topic: SECURITY in both
- Tracking eligible: true in both
- Shelf-life score observed: 75 and 80

The fixture selects the second successful observation (shelf-life 80) while retaining both observed values as provenance.

## Production policy evaluated

- `NOTION_SAVE_THRESHOLD_SCORE = 60`
- `ENABLE_GLOBAL_CALIBRATION = true`
- `GLOBAL_CALIBRATION_MIN_RAW_SCORE = 55`
- `TOP_N_FOR_DEEP_DIVE = 3`

Production `calibrate_candidates()` sends every completed Raw score >=55 into Global Calibration. Production Deep Dive selection then requires a score >= Stock threshold **and** a real persisted `notion_page_id`.

## Result

The correct route for Defense Factory is therefore:

1. Raw screening score 88 clears the raw Stock threshold numerically.
2. Because 88 >= calibration minimum 55 and Global Calibration is enabled, Calibration is mandatory before a final Stock decision.
3. This dry-run does **not** call Calibration because model calls are hard-set to zero.
4. Final score is therefore intentionally unknown.
5. Stock persistence remains false.
6. Deep Dive selection remains false because both final calibrated score and successful Stock persistence are prerequisites.

Expected audit status: `CALIBRATION_REQUIRED`.

## Safety invariants

- Gemini/model calls: 0
- source fetches: 0
- X API: 0
- Apify: 0
- FetchLayer: 0
- Factory/Notion writes: 0
- Calibration execution: 0
- Deep Dive generation: 0
- publication: 0

## Business conclusion

The X -> Factory bridge is behaving conservatively. A high Raw screening score cannot bypass the existing cross-batch Calibration policy or the persisted-Stock requirement. This prevents X-discovered candidates from receiving privileged treatment relative to the four existing Factory sources.

The next provider-using gate, if authorized later, is exactly one bounded Global Calibration request for this one candidate. No additional screening is necessary.
