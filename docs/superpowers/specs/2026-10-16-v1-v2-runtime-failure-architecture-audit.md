# AIIF V1/V2 Runtime Failure Architecture Audit

Date: 2026-10-16
Baseline main: `77e8c1247a4a39969e83828ea44d06602c9b29c5`

## Goal

Prevent a local fix from causing a failure in another runtime path. Preserve the current fail-closed publication policy while separating article quality failures from operational/provider/asset failures.

## Non-negotiable constraints

- V1 remains Production authority.
- V2 remains shadow/diagnostic and must not mutate Production.
- Never mark an article Ready unless the existing publication/asset/persistence contracts pass.
- Do not lower quality thresholds or bypass eyecatch integrity checks.
- Do not add unbounded provider retries.
- `Ready == 0` by itself is not an error; a valid no-publish day must remain possible.
- A quality-eligible article lost because of provider/asset/persistence infrastructure must be observable and retryable.

## Observed runtime failures

| Area | Runtime evidence | Production impact | Shared-risk note |
| --- | --- | --- | --- |
| V1 Daily | Run 38886979795 completed GitHub-success but Ready=0 after a quality-passed article hit eyecatch/asset failure and persistence failure | High | Eyecatch uses shared Gemini runtime plus publication asset contract |
| V1 Gemini | Same run: multiple 503/provider failures across configured models | Medium/High | Provider stack is installed before article/publication layers |
| V2 Shadow | Run 38891214263: provider returned, strict Evidence contract rejected output as `provider_evidence_contract_invalid` | No direct Production mutation | Contract subtype is collapsed, limiting diagnosis |
| X Discovery | Same Daily family: 20 profiles, 0 signals, 20 provider errors | Medium acquisition degradation | Additive source; must not block four-source Daily |
| Operational outcome | Daily workflow can be green while an otherwise publishable candidate is lost operationally | High observability risk | Must distinguish valid zero-yield from infrastructure loss |

## V1 dependency chain

`production_pipeline.py` -> canonical `runtime_layers.py` -> `pipeline.main()` -> Deep Dive generation/quality gates -> public eyecatch generation -> eyecatch publication contract/upload -> Notion persistence -> Ready record -> note fan-out.

The current runtime order installs provider resilience before publication and eyecatch wrappers. Therefore provider changes can have a larger blast radius than a renderer-only correction and must not be the first speculative fix.

## Proven contradiction to reproduce first

`run178_eyecatch_editorial_layout_optimizer.py` documents a zero-retry safe fallback: if Gemini/provider/JSON/validation/geometry fails, it calls the existing deterministic `generate_note_editorial_eyecatch`.

However `editorial_eyecatch.generate_note_editorial_eyecatch` derives the headline through `editorial_hook_from_title(title)`, whose default `max_chars=34` truncates long titles with an ellipsis. The renderer then rejects any headline that differs from the full public title or contains an ellipsis by raising `ValueError("Cannot render a complete eyecatch title with the legacy fallback")`.

This means the documented safe fallback is not safe for a long valid public headline. A provider/layout failure can therefore propagate into no eyecatch instead of deterministic recovery.

## Repair order

1. **V1 eyecatch deterministic fallback contract** — prove with RED test; make long exact titles render without provider dependence and without truncation.
2. **V1 eligible-output loss classification** — ensure operational loss after quality success is explicit/retryable without treating every zero-Ready day as failure.
3. **Shared Gemini resilience** — change only if run evidence and tests show current bounded fallback is insufficient after the local eyecatch defect is removed.
4. **V2 Evidence observability** — preserve strict rejection while retaining the exact contract-failure subtype in diagnostics.
5. **X Discovery provider errors** — isolate from core four-source Daily and repair separately.

## Cross-system regression gates

Every implementation PR must verify the directly changed unit plus these invariants as applicable:

- exact public headline is preserved; no ellipsis/truncation;
- 1280x670 PNG contract remains valid;
- provider failure does not create an extra unbounded call;
- V1 Ready still requires publication/asset/persistence success;
- V2 remains diagnostic-only;
- note delivery and Cross DB contracts are not weakened;
- synthetic/provider-free execution remains zero-API.

## Current conclusion

Start with the renderer fallback contradiction because it has the smallest blast radius and directly intersects the V1 failure. Do not change shared provider routing until the fallback is proven healthy. This ordering minimizes the chance that a provider-layer fix changes V1, V2, Product Review, or other Gemini consumers simultaneously.
