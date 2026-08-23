# Run109 Subscriber Inventory Bootstrap — Integration Validation

Date: 2026-08-23

## Verdict
PASS. The user-supplied Run108 source tree was verified first, then the Subscriber Inventory Bootstrap was integrated as a manual, product-only path. Run108's existing article/Fact/Evidence/Reader-First behavior remains regression-clean.

## 1. Supplied Run108 source verification
The supplied archive `AI_Intelligence_Factory_Run108_HumanEditorialNaturalness完成版_2026-08-23(1).zip` was validated before modification.

- ZIP integrity: PASS (`unzip -t`, no compressed-data errors)
- Existing Run108 `SHA256SUMS.txt`: **2567 / 2567 matched**
- unittest from the supplied tree: **456 / 456 PASS**
- pytest from the supplied tree: **456 passed + 10 subtests**
- Synthetic Full from the supplied tree: **500 / 500 PASS**
- Synthetic critical failures: **0**
- Synthetic major failures: **0**
- Synthetic production write isolation: **true**

Therefore the uploaded archive is accepted as the Run108 integration baseline.

## 2. Falsification of the original bootstrap idea
The original idea — promote the highest Screening Score legacy rows until the paid DB reaches about 30 records — was rejected because:

1. Screening Score measures discovery/screening interest, not paid-product adoption value.
2. High-scoring legacy rows include incidents, news, price events, and opinion pieces alongside durable technologies.
3. `ASSESSED` alone is not sufficient inventory: a record can still be commercially thin if Risk / Best For / Avoid For / Evidence / Rationale are missing.
4. Raw Subscriber DB row count can be inflated by blank/manual/incomplete rows.
5. Accelerating the existing Daily Product Review lane directly would compete with free-article acquisition and persistent Gemini quota.
6. A mandatory 30-record quota could pressure the system to weaken Evidence or manufacture ADOPT/TEST/WATCH/AVOID diversity.

Run109 therefore treats 30 as a stretch target, not a forced promotion count.

## 3. Final architecture
### Plan mode — zero Gemini
`inventory_bootstrap.py plan`

- Notion read-only
- selects only eligible `LEGACY_PENDING + RESOLVED + due + Primary URL present` records
- computes **Bootstrap Priority**, explicitly separate from Adoption Score
- discounts event/news/opinion-shaped rows
- rewards durable primary-source surfaces and useful source context
- prevents one discovery source from dominating the planning window where alternatives exist
- calculates launch readiness from complete sellable records, not raw row counts

### Apply mode — manual only
`inventory_bootstrap.py apply`

- requires literal `CONFIRM_BOOTSTRAP`
- re-computes the Plan against the same before-snapshot
- passes an **ordered Canonical Entity ID allowlist** into `pipeline.py`
- uses the existing Run108 Product Review / Evidence / History / Subscriber-sync implementation as the only assessment authority
- does not create a second assessment engine

### Integrated `pipeline.py` product-only branch
When `INVENTORY_BOOTSTRAP_ACTIVE=true`:

1. normal source acquisition is bypassed
2. Article Audit reset is bypassed
3. normal article-DB preflight is bypassed
4. Product Hunt acquisition preflight is bypassed
5. Decision Intelligence / History / Subscriber schema preflight remains fail-closed
6. persistent Gemini counter identity is validated before review
7. only `run_product_reviews()` runs
8. then `run_product_delivery_maintenance()` performs Subscriber sync
9. pipeline returns immediately

This is stronger isolation than the original patch-kit approach that relied on setting all fetch/deep-dive limits to zero inside normal `main()`.

## 4. Plan-to-Apply consistency
Run108 originally sorts legacy Product Review candidates by Screening Score. That is correct for normal Daily and remains unchanged.

Run109 changes this **only when manual Bootstrap is active**:

- no allowlist -> Product Review returns no candidates (fail-closed)
- allowlist present -> only reviewed Plan candidates are eligible
- selection order follows the Plan order, not Screening Score
- normal Daily still uses the original Screening-Score ordering and Phase 2 legacy reservation logic

## 5. Sellable inventory definition
A paid-product record counts toward inventory only when all of the following are present:

- `Assessment State = ASSESSED`
- `Tracking Eligibility = true`
- not archived
- Canonical Entity ID
- valid Primary URL
- Adoption Score
- Adoption Status in ADOPT / TEST / WATCH / AVOID
- Evidence Confidence in LOW / MEDIUM / HIGH
- Production Readiness in LOW / MEDIUM / HIGH
- Short Rationale
- Main Risk
- Best For
- Avoid For
- Primary Evidence URLs

Subscriber-visible count independently applies the same product-completeness principle, preventing blank/manual/incomplete rows from inflating launch readiness.

## 6. Default launch-readiness heuristics
Defaults are business readiness heuristics, not quality-gate overrides:

- Complete Sellable Assessment >= **24**
- Stretch target = **30**
- Adoption Status diversity >= **3**
- Category diversity >= **4**
- Source diversity >= **2**
- MEDIUM/HIGH Evidence Confidence ratio >= **80%**
- reviewed within 30 days >= **80%**
- complete Subscriber-visible inventory >= **24**

The system must not manufacture status distribution to satisfy these heuristics. If diversity is naturally low, the candidate pool should be widened instead.

## 7. Integrated regression results
After integration into the supplied Run108 tree:

- Bootstrap dedicated tests: **24 / 24 PASS**
- Full unittest discovery: **480 / 480 PASS**
- pytest: **480 passed + 10 subtests**
- Synthetic Full: **500 / 500 PASS**
- Synthetic critical failures: **0**
- Synthetic major failures: **0**
- Synthetic production write isolation: **true**
- compileall: **PASS**
- GitHub Actions YAML: **6 / 6 PASS**

## 8. Existing core files unchanged
Byte comparison against supplied Run108 confirms these remain identical:

- `decision_intelligence.py`
- `subscription_attribution.py`
- `regression_suite.py`

The production behavioral modification is intentionally concentrated in a small `pipeline.py` bootstrap hook plus new bootstrap-specific files/tests/workflow.

## 9. New/changed production files
- `pipeline.py` — product-only Bootstrap branch + ordered allowlist hook + dedicated preflight
- `inventory_bootstrap.py` — zero-API Plan / guarded Apply / readiness audit
- `.github/workflows/inventory-bootstrap.yml` — manual-only workflow, no schedule
- `tests/test_inventory_bootstrap.py`
- `tests/test_run109_inventory_bootstrap_integration.py`
- `inventory_bootstrap_artifacts/README.md`

## 10. Recommended operating sequence
1. Deploy Run109 code.
2. GitHub Actions -> **Subscriber Inventory Bootstrap** -> `mode=plan`.
3. Inspect the plan artifact. No Gemini request is used.
4. Only after review, run `mode=apply` with `max_reviews=4`, `product_request_budget=6`, `confirm=CONFIRM_BOOTSTRAP`.
5. Inspect Product Review results, History, Subscriber sync, and launch blockers.
6. Repeat small batches. Do not run a 30-item one-shot assessment.
7. Stop Bootstrap when launch readiness is reached or when evidence quality becomes the limiting factor.
8. Return to normal Daily as the long-term freshness mechanism.

## Final assessment
Run109 is suitable as the integrated successor candidate to Run108. The bootstrap accelerator is isolated from free-article production, reuses the existing authoritative Product Review path, preserves persistent-budget safety, and does not weaken Evidence or publication gates.
