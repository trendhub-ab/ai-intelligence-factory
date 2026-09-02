# Repository Cleanup Manifest — 2026-09-02

## Baseline

- Production baseline before cleanup: Run199
- Baseline main commit: `550c2197a68bf37d9bc48d9c1db2dce683492fa3`
- Baseline Repository-wide Falsification Guard: SUCCESS
- Cleanup branch: `run200-repository-consolidation`
- Intent: repository organization only; no production/runtime behavior change

## Safety principles

1. A file with any proven production, workflow or test dependency is retained.
2. Ambiguous files are retained rather than guessed obsolete.
3. Historical documentation is archived, not destroyed.
4. Operational state and published assets are preserved in place.
5. Runtime-layer consolidation/renaming is deferred unless a dedicated compatibility refactor proves behavioral equivalence.
6. Cleanup must pass repository-wide falsification on a PR before merge to `main`.

## Archived from repository root

The following historical Run documents were moved byte-for-byte to `root-run-docs/` in this archive directory. Their Git blob SHA was reused during the move, so file content did not change.

- `RUN177_PAID_FUNNEL_ALIGNMENT.md`
- `RUN178_EYECATCH_EDITORIAL_LAYOUT_OPTIMIZER.md`
- `RUN179_EYECATCH_FONT_REFINEMENT.md`
- `RUN180_EYECATCH_SEMANTIC_LAYOUT.md`
- `RUN184_NOTE_DRAFT_AUTOMATION.md`
- `RUN184_NOTE_LOGIN_METHOD.md`
- `RUN190_NOTE_PERSISTENT_CLOUD.md`
- `RUN196_NOTION_RATE_LIMIT_AUDIT.md`

## Explicitly retained active production code

### Production runtime layers

`production_pipeline.py` proves that these are active runtime layers and they are therefore retained unchanged:

- `run172_production_reliability.py`
- `run173_operational_yield.py`
- `run174_monthly_digest_integrity.py`
- `run175_semantic_fact_precision.py`
- `run176_scope_fidelity.py`
- `run177_paid_funnel_alignment.py`
- `run178_eyecatch_editorial_layout_optimizer.py`
- `run179_eyecatch_font_refinement.py`
- `run180_eyecatch_semantic_layout.py`
- `run181_eyecatch_visual_balance.py`
- `run182_eyecatch_conclusion_emphasis.py`
- `run183_eyecatch_emphasis_scale.py`
- `reader_value_review_bridge.py`
- `run194_publication_contract.py`

### note draft safety stack

The existing layered note stack is retained unchanged because current entrypoints depend on it:

- `note_draft_automation.py`
- `run185_note_ready_legacy_skip.py`
- `run186_note_header_image_resilience.py`
- `run187_note_editor_readiness.py`
- `run188_note_header_upload_fallback.py`
- `run189_note_editor_route_gate.py`
- `run190_note_persistent_cloud.py`
- `run191_note_crop_dialog_resilience.py`
- `run193_note_official_header_upload.py`
- `run194_note_current_contract.py`
- `run194_note_persistent_cloud.py`
- `run194_publication_contract.py`
- `run199_note_vm_preflight.py`

The current `note-create-draft.yml` preflight/pinned-sync-id/conditional-VM design is preserved.

## Explicitly retained workflows

Several similarly named workflows were audited and retained because their roles are distinct:

- `regression.yml` — zero-provider Synthetic Regression
- `regression-test.yml` — manually dispatched real-article/model regression
- `note-cloud-preflight.yml` — GCP VM/self-hosted runner/Chrome infrastructure diagnostic
- `note-create-draft.yml` — actual private note draft workflow with publish-safe candidate preflight
- `run130-portfolio-test.yml` — PR guard for current portfolio policy surfaces

No workflow was deleted solely because its filename contains an older Run number.

## Operational state and published assets — DO NOT CLEAN AS ARTIFACTS

These are intentionally preserved in place:

- `.runtime/`
- `observed_history/`
- `source_roi_history/`
- `deferred_deep_dive/`
- `eyecatch_images/`
- production `assets/`

They may contain state required for quota continuity, learning history, source ROI, deferred work, or URLs already referenced from Notion. Any future migration requires a separate reference audit.

## Branch inventory finding

At audit time the repository exposed 71 branches, while the documented long-lived branch policy intends only:

- `main`
- `feature/x-intelligence-layer`
- `integration/main-run147-reconciliation`

Most historical Run/fix/ops branches are administrative cleanup candidates after their commits are confirmed preserved in `main`, merged PRs, tags, or archive records. Branch deletion is deliberately kept separate from source-tree cleanup because deleting refs has different rollback semantics from moving files in a branch.

## Deferred complexity — intentionally not changed in Run200

The following may look complex but are not safe to collapse as a documentation-only cleanup:

- the Run172–Run183 production patch stack;
- the Run185–Run199 note safety stack;
- historical Run-numbered tests that still assert current invariants;
- operational workflows with superficially similar names;
- published eyecatch assets and persisted operational JSON history.

A future semantic-module refactor may reduce those layers, but only as a dedicated behavior-changing engineering project with explicit equivalence tests. Run200 does not attempt it.
