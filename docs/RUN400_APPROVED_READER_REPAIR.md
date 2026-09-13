# Run400 — Approved Apply Reader Repair Reuse

## Problem

Run399 introduced the new candidate origin `approved_article_apply`. The canonical Run208/360 Reader Repair policy already allows a bounded reader-only repair for safe fresh/article-revalidation candidates, but the new Run399 origin was not recognized as equivalent. A real Run399 production apply therefore generated a manuscript, passed Publication readiness, retained one Deep Dive request, then stopped with `reader_value_review_no_retry` instead of spending that final request on the existing bounded Reader Repair.

## Decision

Run400 does not create a new repair algorithm and does not weaken any gate.

Only when `candidate_origin == approved_article_apply`, Run400 delegates the retry-policy decision to the already-installed canonical policy using `article_revalidation` semantics. All other origins are forwarded unchanged.

## Safety contract

- Owner-approved Run399 remains the only installation point for Run400.
- Fact / Evidence / Publication / Reader gates are unchanged.
- Evidence sufficiency and `decision_scope_safe` remain prerequisites owned by Run208/360.
- Existing per-candidate retry ownership remains authoritative.
- Reader Repair remains bounded; Run400 adds no loop and no additional budget.
- The existing Deep Dive request budget remains authoritative. If no request remains, no repair can run.
- A repaired manuscript is fully re-gated and must still return `accepted` before persistence.
- No note.com public-release action is added.
- X logic is untouched.

## Business effect

The change improves yield from already-paid/consumed generation attempts: when a manuscript is factually safe but reader accessibility alone blocks Ready, the final already-budgeted request can repair the article instead of being discarded. This preserves quality thresholds while reducing full-regeneration waste.

## Current release handoff

If the approved RubyGems article becomes `accepted`, Run399 persists it and dispatches Note Ready synchronization. The existing `/aiif note draft` path then creates a private note draft only. Final public release remains manual.
