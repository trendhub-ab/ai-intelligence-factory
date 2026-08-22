# Run107 Eyecatch Regression Test Sync Validation — 2026-08-23

## Root cause
Run106 correctly replaced the asymmetric fixed lower-card X coordinates with `_eyecatch_centered_pair_boxes()`. A legacy Run99 regression test still asserted that the removed fixed coordinate string existed in `generate_eyecatch_image()`, causing GitHub Actions to fail even though the new layout implementation and Run106-specific tests passed.

## Fix
Only `tests/test_pipeline_safety.py` was updated. Production eyecatch code is unchanged from Run106.

The legacy layout test now validates the current contract:
- outer card remains `(60, 78, 770, 592)`
- lower cards use `_eyecatch_centered_pair_boxes()`
- lower box width remains `314`
- gap remains `18`
- text stacks still use measured-bounds centering
- left and right margins are equal
- lower-card pair center equals outer-card center

## Production-code impact
None. This release synchronizes the stale regression assertion with the approved Run106 geometry.
