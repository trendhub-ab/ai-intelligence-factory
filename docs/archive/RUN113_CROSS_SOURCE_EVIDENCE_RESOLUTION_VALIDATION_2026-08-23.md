# Run113 Cross-Source Evidence Resolution — Validation Report

Date: 2026-08-23
Baseline: Run112 Product Review Category Resolution
Status: Candidate complete / not a deployment declaration

## 1. Purpose

Run112 Bootstrap Apply exposed a production-path bottleneck: high-priority legacy candidates could consume the manual Product Review inspection quota while failing Evidence-to-Decision Sufficiency before Gemini. In the observed failure pattern, GitHub repository candidates were supplemented with GitHub global navigation pages such as `/features/copilot` rather than repository-native evidence, and an ArXiv PDF could be retrieved without flipping `primary_source_resolved` to true.

Run113 fixes the evidence-resolution layer across GitHub, ArXiv, Hacker News, and Product Hunt, while preserving the existing Product Review assessment logic, Category resolution, Subscriber sync, and normal Daily article pipeline.

## 2. Falsification findings and fixes

### GitHub

**Rejected hypothesis:** scraping the repository HTML and following research-looking links is good enough.

This is false because GitHub repository HTML contains site-wide product/navigation links that can look like AI evidence. Run113 no longer scrapes GitHub repository HTML for Product Review evidence. It reconstructs the exact `owner/repo` identity from Canonical Entity ID / Primary URL, then uses:

- GitHub README API
- GitHub REST repository metadata
- repository-provided homepage
- explicit documentation/source links from README

GitHub global routes such as `/features/*`, `/enterprise`, `/pricing`, `/solutions/*`, `/marketplace`, `/topics/*`, `/collections/*`, and related navigation are rejected as evidence candidates.

### ArXiv

**Rejected hypothesis:** successful PDF supplementation is insufficient unless the abstract landing page was already resolved.

This was false. A successfully retrieved same-paper PDF is first-party primary evidence. Run113 sets `primary_source_resolved=true` when an authoritative PRIMARY_SOURCE supplement succeeds. Legacy ArXiv rows are rehydrated by exact arXiv ID through the official Atom API. The same-paper DOI redirect is treated as redundant and does not waste a supplement slot. The arXiv HTML page may expose explicitly labelled code/repository links, but the substantive paper evidence remains Atom/PDF.

Research-time words such as `current` no longer create a live-product freshness hard blocker merely because they appear inside a paper.

### Hacker News

**Rejected hypothesis:** the discovery source must remain the evidence source.

This is false for legacy rows. If Canonical Entity ID / Primary URL identifies a GitHub repository or arXiv paper, Run113 promotes the evidence source to GitHub/ArXiv while retaining Hacker News as discovery metadata. An external author/original source can be primary evidence. Secondary news reports remain insufficient authority for paid Product Review.

### Product Hunt

**Rejected hypothesis:** a Product Hunt post is first-party product evidence.

Run113 keeps Product Hunt as a discovery source. Product Review requires an external official product URL, docs, repository, or other authoritative source. A Product Hunt listing itself is not promoted to product primary evidence.

### Legacy Technology rows

Legacy `Source Summary` is useful discovery context but is not silently treated as verified first-party evidence. Run113 reconstructs source identity only from explicit persisted facts: Canonical Entity ID, Primary URL, Evidence URLs, and aliases.

## 3. Review-slot semantics

**Rejected hypothesis:** `max_reviews=3` should mean inspect only the first three candidates.

That behavior caused three Evidence-insufficient candidates to end a Bootstrap Apply with zero assessments. In Run113:

- Evidence preflight is zero Gemini.
- Bootstrap may inspect an ordered bounded candidate window before Gemini.
- `max_reviews` caps **Evidence-ready candidates that reach Gemini Product Review**.
- Evidence-insufficient candidates do not consume a Gemini review slot.
- Default manual preflight scan limit is bounded to `min(24, max(max_reviews*4, max_reviews+6))`.
- Transport-like primary fetch failures receive a short 1-day cooldown; substantive evidence gaps retain the normal review cadence.
- Normal Daily candidate selection order and cap are unchanged.

## 4. Gemini-cost falsification

Run112 vs Run113 static call-site count:

- `_generate_via_chat(`: 7 → 7
- `genai.Client`: 2 → 2

Run113 adds HTTP/source-native evidence retrieval only. It does not add a new Gemini assessment or classification pass. Gemini capacity/budget is checked only after Evidence-to-Decision preflight succeeds.

## 5. Dedicated Run113 falsification suite

`tests/test_run113_cross_source_evidence_resolution.py`

13 / 13 PASS, covering:

1. GitHub repository-native API path; repository HTML is not scraped.
2. GitHub global navigation is rejected.
3. Exact legacy ArXiv metadata rehydration.
4. ArXiv PDF success resolves primary evidence.
5. Same-paper DOI does not waste supplement capacity.
6. Product Hunt listing is not promoted to primary evidence.
7. Product Hunt official site can resolve primary evidence and pass authority.
8. HN row with GitHub primary is promoted to GitHub evidence.
9. HN original/author source may resolve primary evidence.
10. HN secondary news cannot become authoritative paid-product evidence.
11. Research `current` wording does not force live-product freshness.
12. Evidence skips do not consume the three Gemini review slots.
13. Transport primary failures receive short cooldown.

## 6. Full regression validation

- Dedicated Run113 falsification: **13/13 PASS**
- Full `unittest`: **510/510 PASS**
- Full `pytest`: **510 passed + 10 subtests passed**
- Synthetic Regression Full: **500/500 PASS**
- Synthetic critical failures: **0**
- Synthetic production write isolation: **true**
- `compileall`: **PASS**
- GitHub Actions YAML parse: **6/6 PASS**

## 7. Scope / unchanged critical modules

Run113 intentionally does not redesign the assessment rubric or article quality logic. Relative to Run112, the core business/output modules below are byte-identical:

- `decision_intelligence.py`
- `subscription_attribution.py`
- `regression_suite.py`

Functional source changes are limited to:

- `pipeline.py` — cross-source evidence resolver, evidence-ready review slots, short transport cooldown
- `inventory_bootstrap.py` — bounded zero-Gemini preflight scan configuration
- `.github/workflows/inventory-bootstrap.yml` — clarifies `max_reviews` semantics
- `tests/test_run109_inventory_bootstrap_integration.py` — updates the prior contract to allow bounded preflight inspection beyond paid review slots
- `tests/test_run113_cross_source_evidence_resolution.py` — new falsification suite

## 8. Remaining live verification

This package deliberately does **not** perform a real Gemini/Notion Apply from the validation environment. The next live Bootstrap Apply is the final E2E check. Acceptance criteria are:

- Evidence-insufficient candidates may be inspected/skipped without consuming `review_slots_used`.
- Up to `max_reviews` Evidence-ready candidates can reach Product Review.
- Generic GitHub `/features/*` URLs do not appear as project Evidence.
- ArXiv PDF/official evidence can satisfy primary-source resolution.
- Successful assessments preserve Run112 Category resolution and sync to History + Subscriber DB.
- No Screening / Calibration / article Deep Dive / quality-retry Gemini activity occurs in Bootstrap mode.

