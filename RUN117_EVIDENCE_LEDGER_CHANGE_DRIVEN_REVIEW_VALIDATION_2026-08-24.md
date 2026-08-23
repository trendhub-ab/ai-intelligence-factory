# Run117 Evidence Ledger & Change-Driven Review Validation

Date: 2026-08-24

## Business decision

Run117 adopts **Evidence Ledger + Change-Driven Review** instead of full-page archiving, hash-only storage, or daily re-review of every Technology.

Why this is the highest-profit design:
- Full-page archiving creates storage/noise/copyright burden disproportionate to subscriber value.
- Hash-only storage cannot prove what evidence supported the old decision.
- Re-reviewing all records with Gemini wastes quota as inventory grows.
- External archive dependence delegates product auditability to a third party.
- Compact evidence extracts + immutable versions + zero-Gemini health checks preserve audit value and trigger paid-cost re-review only on material evidence change.

## Data model

A separate internal **Evidence Ledger DB** stores append-only snapshots. Current Technology state and Decision History remain unchanged.

Required ledger fields:
- Evidence Record
- Technology Entity ID
- Technology Page ID
- Evidence URL (live URL used for future health checks)
- Immutable Evidence URL
- Resolved URL
- Source Version
- Source Type
- Evidence Role
- Retrieved At
- Last Verified At
- Source Health
- Document Hash
- Extract Hash
- Evidence Extract
- Evidence Identity
- Active Snapshot
- Re-review Triggered

Only the newest snapshot for each Technology + live Evidence URL remains `Active Snapshot=true`; older snapshots remain preserved for audit but are excluded from routine health checks.

## Source strategy

### GitHub
- At successful Decision Intelligence persistence time, resolve the current default-branch commit SHA with one zero-Gemini GitHub REST request.
- Store live repository URL separately from immutable `/tree/<commit-sha>` permalink.
- Health checks use README content, not generic GitHub HTML.

### arXiv
- Store version from official Atom entry (`v1`, `v2`, ...).
- Store versioned arXiv URL when available.
- Health checks compare official Atom metadata, not third-party mirrors.

### Web Docs / first-party pages
- Store compact evidence extract and normalized document/extract hashes.
- Health checks parse readable HTML text before comparison.

## Source Health states

- `VERIFIED`: evidence extract still present and document hash unchanged.
- `COSMETIC_CHANGE`: page/document changed but the exact normalized evidence extract still survives. No Gemini re-review.
- `MOVED`: same-first-party URL moved and evidence extract still survives. No Gemini re-review.
- `MATERIAL_CHANGE`: evidence extract is no longer supported by the current first-party content. Accelerate Technology `Next Review` to now.
- `MISSING`: 404/410 or redirect outside the original first-party boundary. Accelerate `Next Review` to now.
- `FETCH_ERROR`: transient/non-200 condition such as 5xx/network failure. Never treated as evidence deletion and never automatically triggers Gemini.

## Cost control

- Evidence health checks: **0 Gemini**.
- Default health-check cap: **20 active snapshots per Daily run**.
- Query order: oldest `Last Verified At` first.
- Material source change does not itself call Gemini; it only moves the existing Technology `Next Review` forward. The normal Product Review scheduler remains the only paid review path.
- Production `_generate_via_chat` call sites remain **7**.
- Production `genai.Client` sites remain **2**.

## Rollout safety

The feature is OFF by default.

1. Provision Evidence Ledger DB.
2. Set `ENABLE_EVIDENCE_LEDGER=true`, but keep `EVIDENCE_LEDGER_REQUIRED=false`.
3. Run `Evidence Ledger Maintenance` workflow in `dry-run` mode.
4. Run bounded zero-Gemini backfill for existing assessed Technology rows.
5. Confirm coverage and source-health behavior.
6. Only then set `EVIDENCE_LEDGER_REQUIRED=true` so future product assessments cannot silently ship without an evidence snapshot.

The backfill is explicitly a **current verification snapshot at backfill time**. It never fabricates historical page contents for decisions made before Run117.

## Dedicated falsification

Run117 dedicated tests: **11 / 11 PASS**.

Coverage includes:
- live URL and immutable URL are never conflated;
- GitHub commit permalink resolution;
- arXiv versioned URL resolution;
- cosmetic page changes do not trigger re-review;
- missing evidence does trigger accelerated review;
- 404/410 are MISSING but 503 is FETCH_ERROR;
- cross-party redirect cannot be accepted as a valid move;
- same-party move with surviving evidence is non-material;
- material source change accelerates Technology Next Review without a Gemini path;
- a newer snapshot deactivates older active snapshots while preserving them;
- feature-disabled mode performs zero ledger network calls.

## Mutation / Negative-Control

Three deliberate defects were injected and each was detected by the dedicated tests:
1. Treat 503 as MISSING -> **KILLED**.
2. Replace live health URL with immutable permalink -> **KILLED**.
3. Never deactivate old active snapshots -> **KILLED**.

Result: **3 / 3 mutations killed**.

## Full regression

Final release validation must show:
- unittest: 551/551 PASS
- pytest: 551 passed + 19 subtests
- Synthetic Full: 500/500, critical=0, production_write_isolation=true
- compileall PASS
- workflow YAML 7/7 PASS
- fresh unzip SHA / UTF-8 filename gate PASS

## Scope control

Run117 intentionally does not change:
- Adoption scoring rules/status hysteresis.
- Product Review Gemini budget semantics.
- Run116 Bounded First-Party Discovery.
- article Quality/Evidence gates.
- Subscriber DB payload; ledger hashes/internal audit fields never cross to paid member-facing DB.
- Decision History meaning.
