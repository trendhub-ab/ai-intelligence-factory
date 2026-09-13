# Run419 — Deterministic Eyecatch Plan Repair

## Background

Run418 correctly restored the RubyGems eyecatch to the canonical Production stack and refused the raw/base template fallback. In the first authenticated real execution, Gemini 3.5 returned HTTP 200, but the Run180 semantic layout plan failed strict validation. No Notion or note mutation occurred.

Run180 validates semantic title, title partition, subheadline partition, kinsoku and font geometry as one plan. A plan can therefore contain a valid bounded semantic title while failing only typography geometry. Normal Production would fall back to the raw deterministic renderer; that fallback is intentionally forbidden for this repair because it is the design path that produced the wrong copy position, color and hierarchy.

## Contract

Run419 keeps the Run180 semantic-title safety boundary unchanged. It may repair only typography geometry after Gemini's one existing `gemini-3.5-flash` `eyecatch_layout` request.

If and only if `Run180._validate_eyecatch_title` accepts the returned `eyecatch_title`, Run419 may deterministically rebuild:

- title line breaks using existing editorial helpers;
- bounded title font size;
- title line gap;
- exact subheadline partition and bounded font size;
- highlight phrase using the existing Run180 highlight validator.

The repaired plan is then passed back through `Run180._validate_layout_plan`. If that final validation fails, Run419 fails closed. It never substitutes the raw `editorial_eyecatch` renderer.

## Cost and model policy

- exactly one logical Gemini request remains allowed;
- model remains `gemini-3.5-flash`;
- Gemini 3.8 is not used;
- no retry is added;
- deterministic repair uses zero model calls;
- the shared Gemini budget lock and persistent quota ledger remain authoritative.

## Visual and mutation boundary

The final renderer remains the already-installed Production stack: Run179/180/181/182/183/296. Therefore the current Production copy placement, navy typography, restrained orange emphasis, brand treatment, background and right-side illustration remain authoritative.

Target identity remains the exact RubyGems page and existing private note draft defined by Run418. The Notion eyecatch is replaced only after a canonical image is produced. The existing note draft is then updated in place, header only, with route/title/body equality checks. No duplicate draft and no public publication are permitted.

## Regression policy

`tests/test_run419_eyecatch_plan_repair.py` proves that malformed geometry can be repaired without changing semantic title/subheadline content, invalid semantic titles remain rejected, no raw renderer is introduced, no second model request is permitted, and no public-release surface is added.
