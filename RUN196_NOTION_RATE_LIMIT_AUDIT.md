# Run196 — Notion rate-limit resilience audit

## Live falsification finding

Run195 passed repository-wide static/zero-provider CI, full unit regression, and synthetic regression. After merge, the main-push Subscriber Decision Brief live sync exposed an external-system failure mode that PR-only tests could not reproduce:

- inventory inspected: 206 member pages
- created before throttling: 5
- unchanged: 125
- errors: 76
- failure class: Notion HTTP 429 `rate_limited`
- Notion returned explicit `Retry-After` / `additional_data.retry_after` delays, but the old Decision Brief transport treated 429 as a permanent page error and continued issuing later requests.

A second cross-workflow contributor was present: Member Presentation Sync and Subscriber Decision Brief Sync both use `NOTION_DECISION_INTELLIGENCE_API_KEY`, but previously had different concurrency groups, so a main-push / ONE-SHOT fan-out could run both writers simultaneously.

## Fix contract

Run196 therefore fixes both layers instead of merely increasing a sleep constant:

1. Every Subscriber Decision Brief Notion GET/POST/PATCH/DELETE is routed through one request helper.
2. HTTP 429 honors Notion's retry delay, with bounded retries and a capped delay.
3. HTTP 5xx receives bounded exponential backoff.
4. Successful requests are paced individually, preventing the two-read unchanged-page path from creating short bursts.
5. Member Presentation and Subscriber Decision Brief share one cross-workflow non-cancelling writer lock.
6. Subscriber sync timeout is increased to allow legitimate Retry-After recovery across the full member inventory.
7. Unit tests reproduce JSON/header Retry-After, 5xx recovery, and per-request pacing.
8. Repository-wide falsification guard makes the shared writer lock and retry transport permanent contracts.

## Safety

- Zero Gemini changes.
- No note publication behavior added.
- No private/undocumented note API.
- PR checks do not run the live Subscriber Notion write step because that step is skipped on `pull_request`.
- The existing fail-closed behavior remains: if a page still fails after the bounded retry budget, the sync reports an incomplete run rather than claiming success.