# Run109 Inventory Bootstrap — Operations

## GitHub Actions recommended path
Open **Actions -> Subscriber Inventory Bootstrap**.

### First: Plan only
- `mode`: `plan`
- `target_inventory`: `30`
- `min_sellable`: `24`

Plan mode is Notion read-only and uses zero Gemini calls.

Review the uploaded `inventory_bootstrap_artifacts/` plan before any Apply.

### Then: small Apply
- `mode`: `apply`
- `target_inventory`: `30`
- `min_sellable`: `24`
- `max_reviews`: `4`
- `product_request_budget`: `6`
- `max_source_share`: `0.60`
- `confirm`: `CONFIRM_BOOTSTRAP`

Do not jump directly to a large batch. Evidence-insufficient candidates are allowed to fail/defer; target inventory is not a quota.

## What Apply is allowed to do
- read Technology Intelligence inventory
- fetch evidence needed by the existing Product Review path
- use Product Review Gemini requests within the configured product budget
- write Technology Intelligence assessment/history through the existing Phase 2 path
- sync sanitized assessed rows to AI Decision Intelligence Subscriber DB

## What Apply must not do
- source discovery crawl
- Screening Gemini
- Global Calibration
- article Deep Dive
- quality retry for note articles
- eyecatch generation/upload
- Article Audit reset/write
- monthly digest generation

The integrated `pipeline.py` branch bypasses these systems rather than relying only on zero limits.

## Stop conditions
Pause Bootstrap if any of the following occurs:
- persistent quota / provider instability makes Product Review unreliable
- Evidence insufficiency dominates the batch
- Subscriber sync does not reflect successfully assessed records
- unexpected Screening / Calibration / Deep Dive Gemini activity is detected
- launch readiness is already reached

## Long-term mode
Bootstrap is a launch-preparation accelerator only. Once inventory is commercially credible, keep the normal Daily pipeline as the source of freshness and incremental assessment.
