# Run271 — Member Body Delta Sync

## Purpose

Run270 production rollout rebuilt 206 Member Presentation DB bodies successfully, but the body phase took approximately 13 minutes 23 seconds. Run169.1 had already removed per-child deletion on generated-only pages, so the remaining steady-state bottleneck was the repeated block GET/match work across all 206 pages.

Run271 changes the operational scope, not the paid-product semantics.

## Current authority preserved

- Run268 Proposal-First business/source contract remains authoritative.
- Run270 Proposal-First Member Surface remains the visible body contract.
- Evidence, Decision Score/status, source data, Deep Tech classification and Notion schema are unchanged.
- ZERO Gemini/model calls and zero new paid APIs.
- Manual Notion blocks remain protected by the existing conservative replacement path.

## Delta-sync contract

`Member Presentation Sync` records `MEMBER_BODY_CHANGED_SINCE` immediately before the property-level presentation sync. The body phase then:

1. queries the Member Presentation DB once;
2. selects only pages whose Notion `last_edited_time` is at or after the cutoff;
3. validates one deterministic generated-body sentinel against the currently installed Run270 body contract;
4. if the sentinel matches, performs block GET/write operations only for the changed pages;
5. if the sentinel mismatches, falls back to a full scan/migration;
6. if `MEMBER_BODY_FORCE_FULL=true` or no cutoff is supplied, preserves the legacy full-scan behavior.

The push-triggered workflow forces full mode because a code change may intentionally change the body contract. Workflow re-runs (`github.run_attempt > 1`) also force full mode for recovery. Manual workflow dispatch exposes `force_full_body_sync` for explicit recovery/migration.

## Expected performance effect

The expensive work is now proportional to the number of Member pages whose presentation properties changed, rather than the full catalog size. A no-change steady-state run should perform only the Member DB query plus one sentinel body validation, instead of reading all 206 generated bodies.

Run271 does not claim a production timing improvement until the post-merge workflow is measured directly.

## Regression requirements

- Missing cutoff => full scan (backward compatible).
- Explicit force-full => full scan.
- Valid cutoff + matching sentinel => only recent pages enter body I/O.
- Sentinel mismatch => full migration automatically.
- Existing manual-note preservation, generated-parent rebuild, visible Run270 headings and zero-model guarantees remain covered by the existing member UX suite.
