# Apply Repository Cleanup

1. Create a backup branch from the current `main`.
2. Replace the working tree with the contents of this clean package **without deleting GitHub Secrets/Variables**.
3. Run `git add -A` so archived moves/deletions are recorded.
4. Confirm that operational state paths remain present: `.runtime/`, `source_roi_history/`, `deferred_deep_dive/`, `observed_history/`, `eyecatch_images/`.
5. Run `python -m unittest discover -s tests -q`.
6. Push to a cleanup branch first, confirm GitHub Actions, then merge to `main`.

Do not bulk-delete `eyecatch_images/` or persistent state directories. The cleanup intentionally preserves them.
