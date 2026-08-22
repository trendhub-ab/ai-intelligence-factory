# Run 102 Publish Yield Precision Validation

Date: 2026-08-22
Base: Run 101 Human Audit Precision

## 1. Profit-maximization proposal falsification

Before implementation, the proposed "SOFT quality should not block publication" policy was challenged from the opposite direction.

### Counterargument A: raising Publish Yield can reduce profit
If weak articles are published merely to increase Ready count, reader trust, follow rate, LP click-through and paid retention can decline. Therefore Run 102 does **not** optimize Ready count in isolation and does not set a Publish Yield target.

Resolution: facts/evidence/decision contradictions remain HARD. Missing decision value such as `action_collapsed_to_generic_monitoring` or `decision_voice_missing` is REVIEW rather than SOFT. A very list-heavy article is REVIEW. Fabricated personal experience is HARD.

### Counterargument B: eliminating retries can reduce acquisition quality
A weak hook or flat title can reduce CTR. Automatically spending another Gemini call on every such defect, however, consumes scarce Free Tier budget and can introduce new hallucinations. There is not yet conversion evidence proving that one extra rewrite pays for itself.

Resolution: hook/title/style-only defects are published with warnings and measured in the market. Core decision-value defects still receive one repair retry.

### Counterargument C: SOFT aggregation could hide a bad article
Several small warnings can coexist. Adding an arbitrary warning-count threshold would violate the current policy against inventing a minimum quality score/threshold and could recreate over-rejection.

Resolution: no new numeric threshold was invented. Material readability defects are classified individually as REVIEW; unknown future Editorial/Human Appeal rules fail-safe to REVIEW rather than being silently treated as SOFT.

### Counterargument D: Retry reduction benefit is not proven by Run 100
Run 100 used six Quality Retry calls; its initial failures generally contained Fact/Publication issues, so Run 102 cannot honestly claim that all or most of those six calls would have been avoided.

Resolution: the code now measures `Retry Avoided (SOFT only)`, `Retry Triggered by HARD`, and `Retry Triggered by REVIEW`. Cost savings will be judged from live data rather than assumed.

Conclusion: the profit-optimal minimum change is not "loosen all Gates". It is to separate safety/decision-value defects from stylistic imperfections, spend API only on the former, and expose both Publish Yield and retry economics.

## 2. Implementation

### Severity model
- HARD_BLOCK
- REVIEW
- SOFT_QUALITY
- OPERATIONAL

Reason rows preserve `reason_code`, `message`, `gate`, and `severity`. Legacy rows without severity are normalized by reason code with fail-safe inference.

### HARD examples
- Fact unsupported/numeric/actor/conditionality errors
- Evidence insufficiency for the core decision
- Publication overclaim / research-to-production leap / score narrative mismatch / negative-evidence omission
- Fabricated personal experience

### REVIEW examples
- Action collapsed to generic monitoring
- Decision voice missing
- No editorial observation when decision/action is also absent
- Over-hedging without a decision
- Material re-edit degradation
- Article over 55% list-like under the existing rule
- Unknown future Editorial/Human Appeal defects

### SOFT examples
- opening_hook_weak
- headline_flattened
- repeated_caveat_phrase
- mechanical ordinal structure
- repetitive AI-like endings
- excessive headings warning
- repetitive fixed introduction
- missing observation/reservation style signal
- mechanical three-reasons phrase
- too many reader questions
- monotonous sentence endings
- deterministic Japanese polish warnings

## 3. State machine

`PASS` / `PASS_WITH_WARNINGS` -> Ready path immediately.

SOFT-only -> no Quality Retry, warning remains in Gate History and Article Audit.

HARD repairable -> zero-API deterministic rescue first, then at most one Quality Retry.

HARD non-repairable Evidence/source gap -> no Quality Retry.

REVIEW decision-value defect -> at most one Quality Retry; if unresolved -> Needs Editorial Review.

Fact FAIL -> never downgraded to Needs Editorial Review.

Explicit Publication FAIL -> remains Quality Failed rather than being mislabeled as Fact failure.

## 4. Observability

Daily Funnel now reports:
- Candidate Publish Yield
- Generated Publish Yield
- Hard Blocked
- Needs Editorial Review
- Ready with SOFT Warnings
- Retry Triggered by HARD
- Retry Triggered by REVIEW
- Retry Avoided (SOFT only)
- Editorial Warning

Article Audit `RUN_SUMMARY.md` adds Disposition and Quality Warnings / Failure Reason. Ready `final.md` records warnings as Quality Notes, not as Failure Reason.

## 5. Regression additions

New Run 102 tests cover:
- Fact/Publication safety remains HARD.
- weak hook and flat title are SOFT and do not spend retry.
- decision-value loss is REVIEW and still gets one repair retry.
- fabricated experience remains HARD.
- materially list-heavy article requires REVIEW.
- non-repairable Evidence gap spends no Quality Retry.
- legacy reason rows are severity-normalized fail-safe.
- unknown future Editorial/Human rules default to REVIEW.
- actual generate_intelligence_report soft-only path performs one generation call and is accepted.
- actual decision-value REVIEW path performs one repair retry and remains unpublished if unresolved.
- Funnel calculates both Publish Yield definitions and retry savings.
- Ready Article Audit exposes Quality Notes and disposition.

## 6. Non-goals preserved

No Fact Gate relaxation. No unconditional Evidence relaxation. No new external API. No Gemini paid-tier assumption. No Publish Yield target. No pricing change. No auto-posting. No Article Audit removal. No production isolation change. No Notion DB redesign.

## 7. Final validation results

Validation rerun after the final Gate-semantics alignment:

- `python -m unittest discover -s tests -p 'test_*.py'`: **424 / 424 PASS**
- `pytest -q`: **424 passed + 10 subtests passed**
- Synthetic Regression Full: **500 / 500 PASS**
- Synthetic critical failures: **0**
- Synthetic `production_write_isolation`: **true**
- Top-level Python compile: **5 / 5 PASS** (`pipeline.py`, `decision_intelligence.py`, `subscription_attribution.py`, `migrate_decision_intelligence.py`, `regression_suite.py`)
- GitHub Actions workflow YAML parse: **5 / 5 PASS**
- New external Python imports versus Run 101: **0**
- Bundled font binaries: **0**

The local validation environment does not provide `google.genai`; the Full Synthetic suite was therefore executed with an import-only stub for `google.genai`. The Synthetic Regression path itself does not send provider calls. Production provider logic was not replaced or modified by that validation stub.

No Publish Yield target was introduced. Run 102 adds measurement, not a fabricated success threshold. Live API savings and live Publish Yield improvement must be established from the next Daily run rather than inferred from unit/synthetic tests.

### Archive re-extraction validation

The release ZIP was also extracted into a clean directory and revalidated:

- `SHA256SUMS.txt`: all entries PASS
- Re-extracted unittest: **424 / 424 PASS**
- Re-extracted pytest: **424 passed + 10 subtests passed**
- Re-extracted Synthetic Regression Full: **500 / 500 PASS**, critical **0**, production isolation **true**
- Mojibake filename scan: **0 suspected filenames**
- Bundled font binaries: **0**
