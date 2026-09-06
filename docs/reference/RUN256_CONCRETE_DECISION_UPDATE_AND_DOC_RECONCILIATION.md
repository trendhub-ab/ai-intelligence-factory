# Run256 — Concrete Decision Update + Documentation Reconciliation

Date: 2026-09-06

## Why

Run250–255 rebuilt the paid member surface, but two gaps remained:

1. The monthly Brief described Decision Update abstractly without guaranteeing a concrete customer-visible explanation of what changed, why it matters, the current judgment, and the supporting evidence.
2. `AI_Intelligence_Factory_最終仕様書.md` still described the older note-membership / DB+Digest product and had not caught up with the Work-First product contract.

## Product change

When a material change exists, the monthly Decision Brief now renders the update concretely in the body using existing Decision History data:

- `変更`: previous status → current status, with score delta when recorded
- `現在の判断`: the existing adoption-status-derived action label
- `理由`: existing change reason / main risk
- `根拠`: existing `追加根拠`; if it is absent, the Brief says so instead of inventing evidence
- `次のAction`: deterministic action text derived from the existing adoption status

If no material change exists, the Brief explicitly renders `重要な判断変更なし` and one monitoring point. The monitoring condition uses the existing meaningful-change contract: Status change, adoption-score movement of at least `MEANINGFUL_SCORE_DELTA`, or a new assessment.

The existing meaningful-change selector and priority order are preserved. Run256 changes presentation of the monthly product, not the canonical Decision, score, status, or Evidence gate.

## Runtime implementation

The Run255 `decision_intelligence.py` blob is preserved byte-for-byte as `decision_intelligence_run255_core.py`.

The current `decision_intelligence.py` is a thin compatibility extension that executes the preserved core in the same module globals and overrides only the monthly digest creation/rendering path. This keeps existing imports and test patching semantics while avoiding a regenerated rewrite of the large Decision Intelligence module.

Regression coverage is added in `tests/test_run256_concrete_decision_update.py` for material-change, no-material-change, schema-preservation, priority-preservation, legacy-section, and zero-provider-call scenarios.

## September 2026 example

`FlowiseAI/Flowise` remains the current concrete editorial example recorded for this Run:

- Official GitHub repository is Archived.
- Current member judgment is AVOID for new adoption.
- Existing Flowise use is treated as maintenance/migration context.
- Next action is to compare currently maintained alternatives.

This example is editorial/product evidence; the runtime implementation itself is generic and does not hard-code Flowise.

## Documentation change

`AI_Intelligence_Factory_最終仕様書.md` was slimmed from a historical accumulation into a current Production contract.

The new document:
- points to current code/tests as authority,
- uses `PAID_PRODUCT_CONTRACT.md` as the paid-product detail contract,
- records Work-First / neutral-subject product semantics,
- removes the obsolete assumption that note itself is the market,
- does not claim an unverified payment provider as Production-complete,
- preserves Daily PAUSED, human-only public release, Evidence/Decision/Deep Tech, zero-provider-call presentation rules,
- keeps detailed old Run rationale in `docs/reference/` and Git history rather than growing the final spec indefinitely.

## Safety

Runtime change is limited to monthly Decision Brief presentation.

- No canonical Decision mutation
- No source score mutation
- No Evidence weakening
- No Deep Tech deletion
- No Notion schema change
- No new provider calls
- Existing meaningful-change threshold and ranking preserved
- Daily remains PAUSED
- Public note release remains human-only
