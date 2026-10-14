# V2-004 Provider-Backed Evidence Implementation Plan

Spec: `docs/superpowers/specs/2026-10-14-v2-004-provider-backed-evidence-design.md`
Base: `3ddd3b24270e4b4a474c984cd98ecf4c8306d93e`
Branch: `design/v2-004-provider-backed-evidence`

## Global constraints

- V1 Production remains authoritative.
- No merge without explicit MERGE GO.
- No live provider run during implementation.
- Deep Dive max one attempt, no retry, no fallback to another model or rank.
- `gemini-3.6-flash` only; no Lite model.
- Artifact-only output; no Notion/note/Production persistence.
- Chat trigger remains exact Issue #71 ChatOps workaround.

## Task 1 — RED provider-backed slice tests

Create `tests/test_v2_shadow_deep_dive.py` first.

Required RED cases:
- strict valid result accepted;
- malformed/non-object/extra-key/missing-key/wrong-type/unknown-code/contradictory-code results rejected;
- evidence points bounded and non-empty;
- one eligible rank-1 candidate causes exactly one injected model call;
- insufficient/provider failure never falls back to rank 2;
- report preserves V1 authority and diagnostic-only state;
- report writer creates only requested JSON file.

Run focused test and observe failure because implementation does not yet exist.

## Task 2 — RED workflow and ChatOps contract tests

Create `tests/test_v2_shadow_deep_dive_workflow.py` and test the existing `run202_chatops_control.py` contract through it.

Required RED cases:
- workflow_dispatch only, exact `RUN_V2_SHADOW_DEEP_DIVE` confirmation;
- contents read only;
- exact `GEMINI_API_KEY` provider credential, no Notion/note/Production credentials;
- pinned checkout/setup-python and artifact upload;
- exact ChatOps command only, malformed variants rejected;
- bridge dispatch target exactly `v2-shadow-deep-dive.yml` with exact confirmation;
- GH_PAT remains the bridge dispatch credential.

Run focused tests and observe RED.

## Task 3 — Minimal provider-backed implementation

Extend the already classified `v2_shadow_observation.py` runner rather than adding a new unclassified root Python surface. Preserve V2-003 `manual_zero_model` as the default mode and add explicit `provider_backed_one_shot` mode for V2-004.

Interfaces:
- `parse_evidence_result(text) -> dict`
- `build_deep_dive_prompt(candidate) -> str`
- `GeminiEvidenceProvider(...).__call__(candidate) -> Mapping`
- `build_provider_backed_observation(...) -> dict`
- existing `write_observation(report, output) -> Path`

The adapter performs one Gemini `generateContent` HTTP POST. It does not implement retry/fallback. The strict parser converts malformed provider response into a controlled failure so V2-001 fails closed. V2-003 zero-model behavior remains physically disabled from Deep Dive by default.

Run Task 1 focused tests to GREEN.

## Task 4 — Workflow and ChatOps implementation

Create `.github/workflows/v2-shadow-deep-dive.yml` and invoke:

`python v2_shadow_observation.py --mode provider_backed_one_shot ...`

Extend:
- `run202_chatops_control.py`
- `.github/workflows/chatops-one-shot.yml`

Exact ChatOps command:
`/aiif run v2_shadow_deep_dive`

Exact downstream payload:
`{"ref":"main","inputs":{"confirm":"RUN_V2_SHADOW_DEEP_DIVE"}}`

Run Task 2 tests to GREEN.

## Task 5 — Canonical fingerprint and verification

Run focused V2 suite, full pytest, specification freshness guard, workflow reference guard, repository falsification guard, Notion access policy guard, and Production smoke through existing PR CI.

If production-surface fingerprint changes, update only the canonical fingerprint in `AI_Intelligence_Factory_最終仕様書.md` to the guard-computed value, then re-run verification.

Open/keep a Draft PR. Review the complete diff and stop before merge.
