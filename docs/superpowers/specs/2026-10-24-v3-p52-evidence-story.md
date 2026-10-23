# AIIF V3 / P5.2 — Recover human-interest prose without invented memory

Date: 2026-10-24 JST. **Experimental Draft · no automatic promotion or publication.**

## Evidence and branching choice

- Actual P5 (Run [#39963513015](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/39963513015)) scored **83/100** in subjective editorial review: FFT 75, Elastic 85, Claude 88.
- Actual P5.1 (Run [#39983666387](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/39983666387)) scored **71/100**: FFT 71, Elastic 69, Claude 73. Although 3/3 C and 16/16 structural checks passed, the outputs lost explanation and reintroduced fabricated historical thoughts.
- This P5.2 branch **starts from immutable P5 PR #852 HEAD** `95016a65701979063f56130bf181bca831661f5d`, not regressed P5.1 PR #854. The human-readable baseline is deliberately retained.

## What was changed (C-only, provider-free)

1. Keep the original concise P5 final editorial polish and add only short clarification about avoiding **unmarked fabricated autobiographical history**, e.g. `サイズをあらかじめ選ぶのが当たり前だと思っていた` and `説明するより自分でやったほうが早いと思ってきた`. This includes first-person omission: a Japanese sentence can invent a personal past without saying `私`.
2. Tie numerical results to the **actor of the claim and the metric/evaluation conditions**, only when in the approved input. **Do not invent** dataset, plan, model, causal relationship, or measured speed when the frozen evidence lacks them. Preserve claims as estimates or third-party criticism where applicable.
3. Preserve sufficient *mechanism explanation* and concrete contrasts, instead of making articles shorter merely to satisfy style cues.
4. Human-review-only diagnostics identify the two actual P5.1 invented-past sentences. No arbitrary automatic fact scoring, AI-semantic entailment claims, forced slang, or added model stage.

## Known input limitations — upstream task, not concealed by style prompts

The frozen Phase 0 `cases.py` source data is preserved exactly for controlled C-only replay and A/B digest compatibility:
- **FFT:** The `10^100` magnitude and the claims about a physically impossible computation model appear in a frozen decision reason without independently verified provenance. An article should not present these as directly measured or as an official OpenAI admission. Before publication, check the actual primary and commentary material, add properly attributed verified data through the normal source-intake process, then re-run existing Fact Gate.
- **Elastic:** `50% / 0.8%` lacks its model/task/metric conditions in the frozen case. Do not invent the qualifiers just because they may be available outside. Source enrichment is required for publishable, defensible precision.
- **Claude:** `additional cost = none` and plan/marketplace permissions must be scoped to current verified eligibility; do not treat all paid plans or all organizations as universally eligible. Source and product conditions should be verified before publication.

## Proof required before acceptance

- Focused unit tests: P5.2 specific content routing in staged C and bundle C; no cross-contamination into B/other stages; human-only diagnostic vs real bad C; preservation of original P5 tests.
- Full offline pytest, repository guards, and CI.
- Optional **separately approved** 3-case C-only generation using the same frozen A/B checkpoint for an actual apples-to-apples **human** review against P5 Run #39963513015. No score increase is claimed from prompt tests alone.
- No modification of main, Production, note, Notion, paid subscriber DB, release or publishing.
