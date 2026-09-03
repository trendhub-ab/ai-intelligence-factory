# Run223 — Technical Claim Precision

Date: 2026-09-04  
Status: Production candidate  
API impact: **0 model/API calls added**

## Why

The first full human audit of a real automated note draft found that the article was structurally strong but still allowed several narrow technical-precision errors:

1. method-specific API values could be collapsed into one generic parameter value;
2. selected/possibly-lossy conversion changes could be generalized into a blanket prohibition;
3. a source expectation/benchmark multiplier could lose its modality and workload caveat;
4. a source publication date could be confused with discovery/analysis/ingestion dates;
5. an obvious Japanese particle typo could survive the final article.

These are publication-quality issues. They must be fixed without weakening Evidence/Fact gates or spending additional Gemini quota.

## Production behavior

`run223_technical_claim_precision.py` installs immediately after Run175 semantic precision and before Run176 scope fidelity.

It adds three zero-model surfaces:

- generation guidance in `build_decision_prompt`;
- high-precision deterministic checks in `validate_fact_gate`;
- local patch instructions in `build_dynamic_retry_instruction`.

### Guard 1 — operation-specific parameters

When the primary evidence exposes different values for the same parameter across methods, the article must not collapse them into one copyable setting. The initial high-precision regression covers the observed `maintain_order` case: `group_by(..., maintain_order=True)` versus `join(..., maintain_order="left")`.

### Guard 2 — breaking-change scope

Wording such as “implicit/ambiguous type conversion is prohibited” is blocked unless the sentence preserves a source-supported qualifier such as selected/some/lossy/information-losing cases.

### Guard 3 — performance multiplier scope

If a multiplier is an expectation, benchmark, measurement or example in the source, the article must preserve that modality/attribution and must not present the result as an unconditional workload-independent guarantee.

### Guard 4 — first-party source dates

Only explicitly named first-party/source publication metadata keys may be used for deterministic date comparison. Generic `date`, crawl/collection timestamps and analysis dates are deliberately ignored. When no single authoritative first-party date exists, the validator does not guess; generation guidance requires omission rather than substitution.

### Guard 5 — obvious Japanese particle damage

A deliberately tiny typo detector blocks known malformed particle sequences such as `によるな処理`. This is not a general Japanese grammar model and must remain high precision.

## Safety invariants

- No Gemini/model request is added.
- Evidence thresholds, Decision scoring and source authority do not change.
- Existing Fact failures are preserved and merged with Run223 failures.
- Retry instructions demand local repair only; they do not authorize new facts or guessed API values.
- Run223 is part of `PUBLICATION_POLICY_FILES`, so any Run223 change changes the automatic Publication Contract policy SHA.
- Pre-Run223 Ready manuscripts therefore fail closed until rebuilt/restamped under the current policy.
- Public note release remains human-only.

## Regression contract

`tests/test_run223_technical_claim_precision.py` covers:

- method-specific `maintain_order` precision;
- blanket conversion-scope rejection;
- expectation/benchmark multiplier scope;
- explicit first-party date matching and rejection of operational date substitution;
- ambiguous-date fail-safe behavior;
- malformed Japanese particle detection;
- the corrected Polars audit excerpt;
- production wrapper installation and failure propagation.
