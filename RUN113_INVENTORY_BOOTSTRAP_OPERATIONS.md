# Run113 Subscriber Inventory Bootstrap — Operations

## Recommended next run

After reflecting this candidate into the GitHub `main` branch and confirming regression workflows are green, run **Subscriber Inventory Bootstrap** manually.

Use:

- `mode`: `apply`
- `target_inventory`: `30`
- `min_sellable`: `24`
- `max_reviews`: `3`
- `product_request_budget`: `6`
- `max_source_share`: `0.60`
- `confirm`: `CONFIRM_BOOTSTRAP`

## Run113 meaning of `max_reviews`

`max_reviews=3` now means **at most three Evidence-ready Gemini Product Reviews**, not “inspect exactly the first three Plan candidates”.

The Bootstrap subprocess can inspect a bounded number of ordered candidates with zero Gemini first. Candidates that cannot support a safe decision are skipped/deferred and the preflight continues until it either finds three Evidence-ready candidates or exhausts the bounded scan window.

For `max_reviews=3`, the default preflight scan window is 12 candidates. It is always capped at 24.

## Source-resolution matrix

| Discovery / Primary shape | Run113 evidence path | Paid Review authority |
|---|---|---|
| GitHub repository | Exact owner/repo → README API + REST metadata → repo homepage/docs | Allowed when technical evidence is sufficient |
| ArXiv paper | Exact ID → Atom metadata → same-paper PDF → explicit code links | Allowed within paper/version evidence scope |
| Hacker News → GitHub | HN retained as discovery; GitHub promoted as evidence source | GitHub authority |
| Hacker News → author/original page | external original page | Allowed when source is not secondary news and evidence is sufficient |
| Hacker News → Reuters/etc. | secondary report | Fail closed until first-party source resolves |
| Product Hunt → official site/docs/repo | PH retained as discovery; official external source fetched | Allowed when authoritative external evidence resolves |
| Product Hunt listing only | PH page only | Fail closed |

## What to inspect in the Apply artifact

Upload the complete `subscriber-inventory-bootstrap-<run_id>.zip`. The audit should inspect:

- `*_inventory_bootstrap_apply.json`
- `*_inventory_bootstrap_apply.md`
- `*_inventory_bootstrap_pipeline.log`

Key log/result fields:

- `attempted` / `inspected` — zero-Gemini evidence candidates inspected
- `evidence_ready` — candidates safe enough to reach Gemini capacity checks
- `review_slots_used` — actual paid Product Review slots consumed
- `saved` — successful assessments
- `evidence_skipped` — evidence-insufficient candidates
- `authority_skipped` — discovery/secondary sources rejected for primary authority

Expected invariant: `review_slots_used <= max_reviews`, and evidence skips do not increment `review_slots_used`.

## Cost control

Run113 adds no Gemini call path. Evidence resolution uses source-native HTTP/API retrieval. Product Review Gemini is called only after evidence preflight passes and still obeys `product_request_budget` plus the persistent project/session quota controls.

## Safety

Bootstrap mode still bypasses normal acquisition, Screening, Global Calibration, article Deep Dive, quality retry, article audit reset, and article generation. The workflow's unsafe-activity detector remains fail-closed.

Do not increase `max_reviews` above 3 until at least one Run113 live Apply artifact is audited. The objective is to verify resolver yield before accelerating inventory growth.
