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

## Expected performance effect

The expensive work is now proportional to the number of Member pages changed since the previous successful member sync, rather than the full catalog size. A no-change steady-state run should perform the Member DB query plus one sentinel body validation, instead of reading all 206 generated bodies.

Run271 does not claim a production timing improvement until the post-merge workflow is measured directly.

## Regression requirements

- Previous successful main run is selected; failed/non-main/current runs are ignored.
- Missing previous-success checkpoint => full scan (fail closed).
- Explicit force-full => full scan.
- Valid cutoff + matching sentinel => only recent pages enter body I/O.
- Sentinel mismatch => full migration automatically.
- Existing manual-note preservation, generated-parent rebuild, visible Run270 headings and zero-model guarantees remain covered by the existing member UX suite.
