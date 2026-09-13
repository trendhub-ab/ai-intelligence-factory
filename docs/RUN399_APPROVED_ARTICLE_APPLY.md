# Run399 — Approved Article Apply

## Purpose

Run399 exists to take one article that already passed the read-only `article_validation` lane and persist that same target through the current Production gates without opening the normal full Daily pipeline.

Current approved target:

`OpenAI agents carried out an undisclosed attack on RubyGems`

The target is exact-match fail-closed. A different selected candidate aborts before generation.

## Contract

- Owner-only exact ChatOps command: `/aiif apply ruby-gems-ready`
- Exactly one existing non-Ready article is selected.
- The current lifecycle state is re-read before mutation.
- Already-Ready and Pending Retry rows are refused.
- Legal safety is re-checked.
- The canonical Production article generator and all current Fact / Evidence / Publication / Reader gates remain authoritative.
- The bounded four-request Deep Dive budget remains authoritative.
- `persist_results=True` exists only in this explicit apply entrypoint.
- Regeneration must return `accepted`; otherwise the workflow fails closed.
- On successful persistence, the existing Note Ready synchronization workflow is dispatched.
- Run399 itself never opens note.com and never performs public release.

## Draft-only release policy

For the current operation, public release is intentionally manual.

After Run399 succeeds and Note Ready synchronization completes, the existing `/aiif note draft` ChatOps command may create one private note draft. The existing note automation explicitly saves a private draft only and performs no public release action.

## Safety invariants

Run399 does not:

- resume scheduled Daily execution;
- enable ordinary article auto-publication;
- modify X logic;
- weaken quality thresholds or publication gates;
- bypass Notion lifecycle checks;
- change the global note publication policy.
