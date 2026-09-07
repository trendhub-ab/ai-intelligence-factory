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

`Member Presentation Sync` resolves `MEMBER_BODY_CHANGED_SINCE` from the **previous successful Member Presentation Sync `run_started_at`** through the GitHub Actions read API. Using the prior successful run as the checkpoint preserves overlap: a page manually or automatically edited after the previous successful run began is reconsidered on the next run, even if the edit happened before the current presentation phase.

The body phase then:

1. queries the Member Presentation DB once;
2. selects only pages whose Notion `last_edited_time` is at or after the previous successful-run cutoff;
3. validates one deterministic generated-body sentinel against the currently installed Run270 body contract;
4. if the sentinel matches, performs block GET/write operations only for the changed pages;
5. if the sentinel mismatches, falls back to a full scan/migration;
6. if GitHub Actions history cannot provide a previous successful checkpoint, `MEMBER_BODY_CHANGED_SINCE` is empty and the body layer deliberately falls back to a full scan;
7. if `MEMBER_BODY_FORCE_FULL=true`, preserves the legacy full-scan behavior regardless of the checkpoint.

The workflow grants only `actions: read` in addition to existing `contents: read` so the checkpoint helper can read its own workflow history. The helper uses the standard library and never logs the GitHub token.

The push-triggered workflow forces full mode because a code change may intentionally change the body contract. Workflow re-runs (`github.run_attempt > 1`) also force full mode for recovery. Manual workflow dispatch exposes `force_full_body_sync` for explicit recovery/migration.

## Why the checkpoint uses the previous run start

Using the current run's immediate pre-presentation time is faster but can miss a generated-body edit made between runs. Using the previous successful run's **start** rather than completion provides a safe overlap window: edits made while the previous run itself was still executing are included on the next run. This can rescan a small changed set once, but it avoids trading correctness for speed.

## Production measurement — 2026-09-07

Run271.1 was measured through the existing Production workflow chain after merge. The measurement is a single no-change steady-state observation, not an SLA.

### Safety full validation

The merge-triggered `Member Presentation Sync` ran in the intended push safety mode with `MEMBER_BODY_FORCE_FULL=true`.

- checkpoint: found
- body mode: `full_forced`
- Member pages: 206
- `scanned_body_pages`: 206
- `skipped_by_delta`: 0
- `sentinel_checked`: 0
- unchanged: 206
- body-step elapsed time: approximately **130.78 seconds**

This confirms that code/body-contract changes still preserve the full migration path instead of forcing delta optimization.

### Normal steady-state delta

A successful `Subscriber Decision Brief Sync` then triggered `Member Presentation Sync` through the existing `workflow_run` path, where force-full was false. The checkpoint resolved to the previous successful main Member Presentation Sync start time (`2026-09-07T01:19:15Z`).

The body step ran from `2026-09-07T01:34:07.9053835Z` to `2026-09-07T01:34:10.2438306Z`, or approximately **2.34 seconds**.

- body mode: `delta`
- `force_full`: false
- Member pages: 206
- `scanned_body_pages`: 0
- `skipped_by_delta`: 206
- `sentinel_checked`: 1
- `delta_fallback_full`: false
- Gemini/model calls: 0
- Notion schema changes: 0

Compared with the Run270 body phase of approximately 13 minutes 23 seconds, this observation is approximately **343.4x faster** and **99.71% shorter**. Compared with the Run271.1 safety full validation above, it is approximately **55.9x faster** and **98.21% shorter**.

These ratios describe this specific no-change Production observation. A future run with changed pages will perform body I/O for that changed subset, so elapsed time is expected to scale with the number of changed pages and external Notion latency.

## Expected performance effect

The expensive work is now proportional to the number of Member pages changed since the previous successful member sync, rather than the full catalog size. A no-change steady-state run performs the Member DB query plus one sentinel body validation instead of reading all 206 generated bodies. The 2026-09-07 Production observation above confirms that this steady-state path is active in the real workflow.

## Regression requirements

- Previous successful main run is selected; failed/non-main/current runs are ignored.
- Missing previous-success checkpoint => full scan (fail closed).
- Explicit force-full => full scan.
- Valid cutoff + matching sentinel => only recent pages enter body I/O.
- Sentinel mismatch => full migration automatically.
- Existing manual-note preservation, generated-parent rebuild, visible Run270 headings and zero-model guarantees remain covered by the existing member UX suite.
