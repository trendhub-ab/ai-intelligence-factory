# Run225 — Screening Stock Lifecycle

## Purpose

Screening Stock is a durable intelligence asset, but it must not become an infinite active queue. Run225 adds a **zero-model freshness lifecycle** so old time-sensitive news stops competing with current decision candidates while historical records remain preserved.

## Lifecycle

- **Fresh** — 0–30 days
- **Aging** — 31–90 days
- **Evergreen** — older than 90 days only when the source is a durable GitHub/arXiv asset and no explicit transient-event signal is present
- **Archive** — older than 90 days and not eligible for the durable Evergreen exception

The thresholds are controlled by `STOCK_FRESH_DAYS` and `STOCK_ARCHIVE_DAYS`, defaulting to 30 and 90.

## Freshness anchor

The deterministic classifier accepts three anchors in this order:

1. current/human `reviewed_at`
2. primary/source `published_at`
3. `analyzed_at` fallback

Raw Screening Stock reconciliation intentionally omits `reviewed_at`, so old source material is not made current merely because it was ingested later. Member-product presentation may use a real current review timestamp, allowing a genuinely re-reviewed item to return to Fresh.

Missing or invalid dates are **Aging**, not Fresh. This is fail-safe: unknown age must not receive a freshness bonus.

## Evergreen exception

The exception is deliberately narrow. GitHub and arXiv represent durable software/research assets that can remain decision-relevant after 90 days. Explicit event language such as outage, incident, acquisition, pricing change or one-time launch/news wording prevents the Evergreen exception.

No Gemini call is used to decide Evergreen status.

## Source DB reconciliation

`stock_lifecycle_reconcile.py` queries only `評価状態 = Stocked` rows in Content Intelligence DB and changes only `更新状態`.

To minimize Notion writes:

- blank `更新状態` = canonical **Fresh** encoding
- `Aging`, `Evergreen`, `Archive` are materialized only when needed
- when an item becomes Fresh again, the lifecycle select is cleared

The reconciler never changes:

- Screening/Decision score
- article state
- Evidence
- judgment/adoption state
- URLs or source text

It never deletes or trashes a page.

Manual operator workflow: `.github/workflows/stock-lifecycle-reconcile.yml`.

- `plan` is read-only
- `apply` requires exact confirmation `RECONCILE_STOCK`
- no Gemini/model API
- no note/publication operation
- does not resume the paused Daily workflow

## Active review queue

`run225_portfolio_lifecycle.py` is installed **after Run131** in `portfolio_inventory_bootstrap.py`.

- Archive records are removed before the existing portfolio planner runs.
- Fresh, Aging and Evergreen continue through the unchanged Run131 ranking/diversity logic.
- Records are not mutated or deleted.

This means archive is a participation state, not a destructive storage state.

## Member homepage

`run225_member_lifecycle_ui.py` operates only at the existing homepage-ranking boundary.

- Fresh / Evergreen rank first using the existing authoritative ranker.
- Aging can fill remaining homepage slots.
- Archive receives no homepage rank.
- Archive records remain searchable/history records in the member database.

Run225 does **not** replace `_source_state`; Run170–Run215 copy/current-authority layers remain authoritative. The lifecycle classifier sees the fully prepared state only after those layers have run.

Member page-body generation remains Run219. No Fact, Evidence, score, decision or copy authority is changed.

## Re-promotion

Archive is reversible. A later authoritative/current review can provide a newer review anchor and classify the member-facing item as Fresh again. Raw source reconciliation remains source-date-based so re-ingestion alone cannot fake freshness.

## Safety invariants

1. zero Gemini/model calls
2. no record deletion/trash
3. no Decision/Screening score changes
4. no Fact/Evidence changes
5. no note public release
6. Daily remains paused
7. unknown date does not become Fresh
8. Run131 and Run170–Run215 authority is preserved inside the active lifecycle set

## Tests

- `tests/test_run225_stock_lifecycle.py`
- `tests/test_run225_member_lifecycle_ui.py`
- `tests/test_run225_portfolio_lifecycle.py`

The tests cover 30/31/90/91-day boundaries, missing/future timestamps, durable Evergreen exception, transient-event override, re-promotion, incremental Notion writes, member homepage exclusion and active portfolio exclusion.
