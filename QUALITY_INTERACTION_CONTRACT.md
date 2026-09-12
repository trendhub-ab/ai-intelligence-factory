# AI Intelligence Factory — Quality Interaction Contract

## Purpose

This contract protects the Gemini article-quality pipeline from cross-layer self-contradictions.
It does **not** loosen Fact/Evidence safety and does **not** bypass Human Appeal, Reader Quality,
Publication Readiness, Final Surface, or Publication Contract checks.

## Core invariant

A deterministic system transform must not manufacture a phrase that a later quality gate rejects
for the same semantic reason.

The first confirmed violation was the WATCH management-code cleanup:

1. `_apply_final_japanese_polish()` translated leaked `WATCH` to `今後の動きを注視する`.
2. `validate_human_appeal_gate()` interprets `注視` / `様子を見る` without a concrete action as
   `action_collapsed_to_generic_monitoring`.
3. Therefore the system could create its own Human Appeal REVIEW condition.

Run357 keeps the Human Appeal rule unchanged. Only the deterministic phrase generated from an
actual uppercase standalone `WATCH` leak is normalized to:

`新しい一次情報が出るまで待ち、出た時点で再評価する`

This expresses the intended WATCH semantics as a conditional decision rather than generic
monitoring and is compatible with the existing concrete-action vocabulary (`待ち`).

## Safety constraints

- Zero model/provider/API calls are added.
- Fact and Evidence severity remain fail-closed.
- Human Appeal unknown reasons remain REVIEW; they are not promoted to HARD by this change.
- The contract does not exempt system-generated text from later quality gates.
- Normal author/model prose containing `今後の動きを注視する` is not silently rewritten unless
  the incoming article actually contained an uppercase standalone `WATCH` management-code leak.
- `article_validation` and `pending_retry_validation` remain on their Run356 Production-parity
  path; `pending_only=True` is intentional and must not be removed.

## Interaction order

The canonical Gemini runtime order remains:

`... -> Run248 -> Run249 Final Surface -> Quality Interaction Contract -> Run194 Publication Contract`

The interaction contract is installed inside `runtime_layers.py` to avoid introducing another
single-purpose `runNNN_*.py` patch module.

## Regression requirements

The regression suite must prove that:

1. leaked uppercase standalone `WATCH` is removed;
2. the legacy self-conflicting phrase is not left behind;
3. the replacement does not match the Human Appeal generic-monitor expression;
4. the replacement does match the existing concrete-action vocabulary;
5. ordinary prose without a management-code leak is untouched;
6. installation is idempotent;
7. the interaction contract remains after Final Surface and before Publication Contract.

## Deferred hypothesis: evidence-backed hedging

The audit also identified a possible tension between strict Fact/Evidence discipline and the
Human Appeal `over_hedging_without_decision` rule. This is **not changed in Run357** because the
report did not demonstrate the false positive on a real Gemini production artifact. Before any
threshold or counting change, the hypothesis must be reproduced on an actual generated article
and falsified against genuinely indecisive prose.
