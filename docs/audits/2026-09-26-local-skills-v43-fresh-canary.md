# Local Skills v4.3 Fresh Canary Result — 2026-09-26

Status: **FRESH ALL-GATE PASS / AWAITING BROADER VALIDATION**

## Candidate
- Subject: `Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure`
- Source: ArXiv
- Canonical primary URL: `https://arxiv.org/abs/2609.30217v1`
- Screening score: 74
- Decision score: 75
- Fresh holdout: true

## Gate result
- Fact: PASS
- Editorial: PASS
- Publication: PASS
- Human Appeal: ACCEPTABLE
- Final disposition: PASS
- all_gate_pass: true
- visible_chars: 1300

## Local Skills stack
- Writer v4.3: `f3076ab88316cf9ada97067aa9af21480dff6459`
- Publication Canonicalizer v4: `414089a14c238f104b2866507ddf8521c2baf420`
- Evidence Boundary: `stage8-v3`
- Unsupported numeric claims removed: 0
- Provider article surface reused: false
- Additional Local Skills provider calls: 0

## Execution boundary
- Run: `36217425671`
- Mode: `local_skills_canary_validation`
- persist_results: false
- Editorial Eyecatch provider calls: 0
- no Notion article/Ready persistence
- no note publication
- no downstream publication fan-out

## Production-path behavior
- Acquisition: collected 60 / safe 52 / observed canary excluded 7 / fresh after dedupe 23
- Rank 1 and rank 2 were rejected by existing Evidence/Source preconditions before any Deep Dive send.
- Rank 3 was the first candidate to reach the single allowed Deep Dive and Local Skills compiler.
- Screening API calls: 1
- Calibration API calls: 1
- Deep Dive API calls: 1
- Gemini attempts: 3/3 successful
- Models: gemini-3.5-flash-lite x2, gemini-3.5-flash x1
- Total Gemini tokens: 28,832

## Validation hygiene
This record is now observed. It must never be reused as a fresh holdout for later
Local Skills changes. It may remain only as historical validation evidence.

The candidate status advances to:
`FRESH_CANARY_PASS_AWAITING_BROADER_VALIDATION`

This fresh PASS validates the exact v4.3 writer / canonicalizer / evidence-boundary
stack against one untouched current Daily candidate through the current Production
acquisition and Gate path. It does **not** by itself prove broad generalization or
authorize normal Production activation.
