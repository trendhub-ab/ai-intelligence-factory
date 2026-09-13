# Run403 — Canonical Pending Target Source

## Problem

A fail-closed Run399 attempt can move the explicitly approved RubyGems page to `Pending Retry`. That state is intentionally absent from `get_regen_test_items()`, so Run402's exact-name scan correctly found zero matches even though the page still existed in Notion.

## Contract

Run399 now resolves the exact owner-approved target across two existing bounded canonical sources:

- `get_regen_test_items(DEFAULT_SCAN_LIMIT, "")` for ordinary non-Ready Deep Dive rows;
- `get_pending_retry_items(DEFAULT_SCAN_LIMIT)` for the canonical Pending Retry lane.

Safety remains fail-closed:

- exact `repo.nameWithOwner` equality is required;
- results are deduplicated by Notion page id;
- exactly one unique page must match;
- zero or multiple unique matches fail before any Gemini call;
- a page whose current lifecycle is `Pending Retry` must have been reconstructed from the canonical Pending Retry source;
- already `Ready` remains refused;
- Run400 Evidence-safe bounded Reader Repair and all current Production gates remain unchanged;
- persistence still requires `accepted`;
- public note release remains manual and out of scope.

Normal Daily, generic article revalidation, and Pending Retry ownership are unchanged.
