# Stage 5 invalid measurement attempt

Workflow run `36183206952` is **not a quality result**.

The run stopped before the first record could enter the Local Writer/Gate stack because the preregistration helper malformed `evidence_urls` while building the holdout snapshot.

Observed snapshot defects:

- Intern-S2-Preview URL was truncated.
- Qwen URL contained an invalid joined fragment.
- Auto-research had an empty `evidence_urls` list.
- The quantum paper URL was truncated.

The selected four records, their order, all structured claims, Publication Canonicalizer v3, and Local Writer v3 remain unchanged.

The repair copies the exact Notion primary/source URL value into each record. Since no Gate result existed before this repair, the corrected rerun is the first valid Stage 5 quality measurement.
