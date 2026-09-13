# Run373 — Zero-API Reader Repair hardening

## Purpose

Run372 proved that provider fallback can survive a transient Gemini 3.8 HTTP 503, but the generated Pending Retry article still failed Reader Value review with three observed reasons:

- `dense_report_cluster`
- `multi_axis_reader_weakness`
- `non_engineer_access_failure`

Run373 improves repair precision without calling Gemini, mutating Notion, reconciling Note Ready, weakening any Gate, or publishing anything.

## Reader Repair contract

The deterministic layer converts exact Reader reason labels into an edit plan. It does not rewrite the article itself.

### `dense_report_cluster`

- one paragraph / one decision point;
- collapse implementation-name and method-name lists that do not change the decision;
- preserve Evidence and material constraints.

### `multi_axis_reader_weakness`

The first three paragraphs should communicate, in order:

1. what changed;
2. what the reader should decide now;
3. the material constraint that could change that decision.

Existing facts may be reordered, shortened, contrasted, and paraphrased in plain language. New facts or fabricated analogies are prohibited.

### `non_engineer_access_failure`

- do not explain jargon with more jargon;
- genericize names/abbreviations that do not affect the Decision;
- keep at most one core technical concept in roughly the opening 600 Japanese characters;
- preserve technical names when identity itself changes the decision.

## Human Appeal interaction

Reader Repair must not fabricate conversational friendliness, anecdotes, experiences, numbers, examples, or comparisons. However, it may improve sentence-length rhythm, direct reader relevance, plain-language contrast, and ordering using only existing facts. This removes the prior self-contradiction where a repair was asked to improve reader pull while effectively being forbidden to change reader-facing flow.

## Fail-closed boundaries

Reader Repair remains eligible only when:

- candidate origin is an explicitly authorized recovery/validation lane;
- Evidence state is `SUFFICIENT`;
- `decision_scope_safe` is true;
- every blocker is an approved Reader REVIEW reason;
- no HARD blocker or Fact/Evidence blocker is mixed in;
- the one-repair allowance has not already been spent.

Reader labels are parsed by exact reason code, not substring matching. This prevents `final_surface_non_engineer_access_failure` from accidentally also activating `non_engineer_access_failure`.

## Model routing regression found during zero-API CI

Repository-wide falsification exposed an unrelated Run371 regression: the historical core three-model pool (`3.6, 3.7, 3.5`) was being mistaken for an explicit operator override. Run373 classifies both historical core defaults as implicit and normalizes fresh Deep Dive to the canonical order:

`3.7 -> 3.8 -> 3.6 -> 3.5`

An explicit recovery override such as `3.8 -> 3.6 -> 3.5` remains explicit and keeps that order before missing fallbacks are appended.

## Zero-API validation result

At head `a067fa92ee88ba71ff17b4141560286dca74c8ec`, all four required PR checks completed successfully:

- Repository-wide Falsification Guard — PASS
- Integration Reconciliation CI — PASS
- Notion Access Policy Guard — PASS
- Workflow Reference Guard — PASS

No Gemini/provider request was made by Run373 while establishing this result.

## Provider-backed validation boundary

The one-time workflow `.github/workflows/run370-pending-retry-validation.yml` is now manual-only (`workflow_dispatch`). Its previous path-based push trigger was removed before changing any live validation configuration, so branch edits can no longer automatically spend Gemini free-tier budget.

The semantic environment-variable typo was corrected at commit `32ad5d4b6e42d2a41cea43f98818fb4ce2443a1e`:

`EVIDENCE_LEDGER_REQUIRED: ${{ vars.EVIDENCE_LEDGER_REQUIRED || 'false' }}`

The workflow remains read-only with these boundaries:

- Pending Retry only;
- at most one candidate;
- at most one Reader-only repair when Evidence is safe;
- explicit model order `3.8 -> 3.6 -> 3.5`, with missing canonical fallback appended by runtime routing;
- maximum six provider-visible attempts;
- `persist_results=false`;
- no branch Note Ready reconciliation;
- no note draft or publication.

No automatic provider-backed run was launched by the trigger-removal/config-fix commit.

## Next live proof requirement

The next Gemini validation must be started explicitly and only after the operator decides to spend the bounded free-tier budget. A successful result is not inferred from zero-API tests: the selected real Pending Retry manuscript must pass Fact/Evidence, Publication, Human Appeal, Reader, and final surface checks in the live read-only lane before any persistence recovery is allowed.

## Non-goals

- no Gate threshold relaxation;
- no deterministic deletion of Evidence-bearing article text;
- no Notion content/status persistence;
- no Note Ready sync from the branch;
- no note draft or public publication;
- no automatic Gemini/provider call in Run373.
