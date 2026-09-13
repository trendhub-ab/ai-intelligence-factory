# Run402 — Exact Approved Target Continuation

## Purpose

Run399 is an explicitly owner-approved one-article persistence lane. A failed Run399 attempt can legitimately move the approved article to `Pending Retry`. The generic revalidation selector excludes `Pending Retry` by design, which previously caused the next eligible article to be selected and then rejected by the target-name guard.

Run402 removes that ambiguity without changing generic Production ownership.

## Contract

- Scan remains bounded to `article_revalidation.DEFAULT_SCAN_LIMIT`.
- Resolve the approved target by exact `repo.nameWithOwner` equality before any generation call.
- Exactly one match is required. Zero or duplicate matches fail closed.
- An already `Ready` target is still refused.
- `Pending Retry` continuation is allowed only after the exact owner-approved target has been resolved.
- Generic `article_validation`, full Production recovery and Pending Retry lanes are unchanged.
- Run400 Reader Repair, Evidence safety, retry ownership, request budget and every publication gate remain authoritative.
- Persistence still requires `status=accepted`.
- note.com public release is not part of this lane; handoff remains private-draft only.

## Regression evidence

`tests/test_run399_article_revalidation_apply.py` covers:

- another first candidate can never substitute for the approved target;
- an exact approved Pending Retry target can continue;
- duplicate exact matches fail closed;
- accepted persistence still uses `candidate_origin=approved_article_apply`;
- rejected regeneration still fails closed.
