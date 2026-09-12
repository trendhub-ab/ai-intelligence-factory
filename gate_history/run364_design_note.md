# Run364 historical Ready recovery

Run362 proved exactly 8 current Notion Ready rows have byte-valid Ready-family manuscripts whose publication-policy fingerprints existed on main history.

Run364 freezes those exact 8 page IDs with title, source, primary URL, manuscript SHA-256, historical policy SHA-256, and historical main commit. Dry-run re-reads live Notion state and blocks the entire batch if any row drifts. Apply requires the exact confirmation token `REBASE_RUN362_PROVEN_8`, appends the existing body byte-for-byte under the current Ready caption, and verifies readback identity.

The remaining 37 rows are outside scope. No quality threshold is relaxed. No model/provider call is made. Existing comment properties are untouched. Public note release is not part of this workflow.
