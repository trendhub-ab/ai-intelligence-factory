# Run410 — Exact approved Quality Failed continuation

## Why

Real approved Apply Run #11 reached the intended Production gates, failed closed on Reader quality, and correctly persisted the RubyGems asset as `Quality Failed` / `Not Planned`. That lifecycle transition removed the exact page from both ordinary Deep Dive regeneration candidates and the canonical Pending Retry queue. Run #12 therefore stopped before any Gemini request with `matches=0`.

The article was not lost. The exact Notion page remained the same asset:

- Article: `OpenAI agents carried out an undisclosed attack on RubyGems`
- Notion page id: `3d9479ff-dca9-819a-814c-e4a0aeb3263f`
- Article Status: `Not Planned`
- Content Status: `Quality Failed`
- Evaluation Status: `Deep Dive`

## Contract

Run410 does **not** add a general Quality Failed retry queue.

Only the explicit owner-approved Run399 lane may continue the exact known page, and only when all of the following still hold at execution time:

1. approval token is valid;
2. expected article title matches exactly;
3. expected Notion page id matches exactly;
4. the page is not `Ready`;
5. Content Status is exactly `Quality Failed`;
6. Evaluation Status is `Deep Dive` when present.

The fallback performs a direct GET of the approved page id. It never queries or scans the wider Quality Failed/Stock population. Therefore another Quality Failed article cannot be substituted just because it has a similar title or state.

## Reconstruction

When the canonical Deep Dive and Pending Retry sources contain no exact approved match, the live approved page supplies only the metadata needed to call the same Production generation path: source URL, source summary, source, engagement, screening score and screening reason. All existing Fact, Evidence, Reader, Human Appeal and Publication gates still execute normally.

## Safety invariants

Run410 changes no quality threshold and no model budget. It does not relax Reader Repair ownership, provider fallback, legal safety, Notion persistence requirements or Ready semantics. Normal Daily, ordinary article validation, Pending Retry handling and X logic are unchanged. No note.com action occurs in this lane.

A successful accepted persistence may dispatch the existing Note Ready sync. Public note publication remains outside this task; the handoff after Ready is private draft creation only.
