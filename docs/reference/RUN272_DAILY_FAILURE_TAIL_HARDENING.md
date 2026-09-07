# Run272 — Daily Failure-Tail Hardening

Date: 2026-09-07  
Production source of truth: `main`  
Implementation PR: #152  
Merged implementation commit: `efe2d361e757277ad2cf0ced341cd1c84bf189f8`

## 1. Trigger observation

Run `34075019008` was investigated adversarially rather than treating the top-level 45-minute cancellation as the root cause.

Observed facts:

- Production itself completed; the top-level cancellation occurred downstream in Product Review.
- `product.delivery_maintenance` consumed roughly 933.9 seconds, dominated by repeated arXiv retry chains during Evidence Health.
- OfficialVendor values such as `Sep 3, 2026` / `September 2, 2026` could reach Notion `date.start` unchanged and deterministically produce HTTP 400.
- Extending the global Daily timeout would hide the failure tail and increase cost exposure rather than fixing the causal paths.

## 2. Contract changes

### 2.1 Notion date boundary

Acquisition and source normalization continue to preserve the source-provided date string. This protects existing Evidence/current-state contracts such as Run269.

At the Notion payload boundary only:

- valid ISO date/datetime values are preserved;
- known date-only vendor formats are canonicalized to `YYYY-MM-DD`;
- malformed/unknown values fail closed to an empty Notion date;
- missing precision is not invented.

The first attempted implementation normalized the acquisition-layer value and was rejected by existing Run269 tests. The final design therefore keeps raw source Evidence and normalizes only for persistence.

### 2.2 arXiv Evidence Health circuit

Evidence Ledger already classifies provider transport failure as `FETCH_ERROR` with `material=False`. Run272 preserves that semantic.

After the first arXiv `FETCH_ERROR` in one maintenance run:

- a run-local arXiv circuit opens;
- remaining arXiv health candidates are deferred for that run;
- deferred arXiv candidates are not written back as MISSING, MATERIAL_CHANGE, or other Evidence mutations;
- non-arXiv Evidence Health checks continue;
- the circuit is not persisted across runs.

The design intentionally avoids converting provider unavailability into Evidence disappearance.

### 2.3 Product Review child deadline

`daily_portfolio_review.py` keeps the existing Product Review request-budget contract but changes the child `pipeline.py` execution from an effectively oversized wait to a bounded default of **600 seconds**.

On child timeout:

- partial stdout/stderr still pass through the unsafe-activity detector;
- unsafe partial activity remains a hard failure;
- otherwise the result is structured as deferred (`bounded_child_timeout`) rather than allowing the child to consume the entire Daily deadline.

The global Daily workflow timeout remains **45 minutes**.

## 3. Explicit non-changes

Run272 does not:

- increase Gemini RPD/RPM/TPM or retry budgets;
- change Run268 four-source architecture;
- weaken Fact / Evidence / Decision gates;
- treat Gemini 503 as success;
- change public-release policy;
- change Notion destination authority;
- extend the global Daily timeout;
- add a paid API.

## 4. Falsification history

The implementation was deliberately revised after CI rejected two unsafe assumptions.

1. Acquisition-layer date normalization broke the Run269 raw/current-state Evidence contract. It was removed; normalization now occurs only at the Notion boundary.
2. Exporting the date helper through `source_normalization.install()` enlarged a previously fixed public compatibility surface. It was removed from the installed/exported surface.

This is part of the Run272 contract: the fix must remain a narrow reliability boundary, not broaden source semantics or public modularization contracts.

## 5. Verification before merge

Final implementation head passed:

- Repository-wide Falsification Guard
- Integration Stability / Reconciliation
- full deterministic pytest: **1795 passed**
- Synthetic Production smoke: **30/30**, critical failures 0, production write isolation true
- Notion Access Policy Guard
- Run269 Live Acquisition Smoke

No Production Daily rerun or extra Gemini consumption was required to validate the code change.

## 6. Files changed by implementation

- `source_normalization.py` — parsing helper retained as internal/non-installed support while raw source date contract remains unchanged
- `notion_payloads.py` — persistence-boundary date validation/canonicalization
- `product_delivery_maintenance.py` — run-local arXiv circuit / deferred accounting
- `daily_portfolio_review.py` — bounded Product Review child timeout
- `tests/test_run272_daily_failure_tails.py` — zero-API regression coverage

## 7. Current operational rule

When a provider is degraded, spend less time proving the same outage repeatedly. Preserve Evidence semantics, fail closed on persistence-shape errors, and bound optional/secondary work before the global workflow deadline is consumed.
