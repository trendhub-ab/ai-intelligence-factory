# AIIF V3 — Independent Creative Writer Implementation Plan (2026-10-25)

Parent: `docs/superpowers/specs/2026-10-25-v3-independent-creative-writer-canonical.md`.
Base/restore SHA: `4032060c6b9919ab2a05849e5607d666f503361f`.
Owner authorization: adopt independent writer architecture; **no authorization for paid API experiments, note/Notion writes, Production changes or merge**.

## P0 — lock protections and archive constraints (this branch)

1. Branch from exact main SHA. Record it in the canonical spec.
2. Files changed only in the four explicit P0 paths. No V1/V2/Classic/Production edits.
3. Add one pure typed evidence-to-writer-prompt boundary and deterministic offline tests.
4. Run `python -m pytest -q tests/test_v3_writer_independent.py`; then full regression/guards using existing CI in a draft PR. Tests demonstrate *contract safety*, not editorial quality.
5. Compare against baseline: `git diff --name-only 4032060c6b9919ab2a05849e5607d666f503361f...HEAD`. Reject paths outside P0 allowlist.

## P1 — diagnosis without extra API

1. Keep encrypted blind manuscript set and keys outside public git. Reuse last human editorial comparison; no raw private article bodies or arm-label key committed.
2. Compare where Writer Reaction / Discovery / Shift insights disappear in Persona Article Generation versus Fact-Safe Review.
3. Develop source-scoped atomic fact packs including mechanism/limitations. If mechanism absent, record uncertainty rather than providing the Writer an invented explanation.
4. Freeze a short candidate creative brief; version and hash, never adjust after looking at a single score.

## P2 — bounded paired experiment (explicit owner GO required)

1. Baseline P5 and minimalist Creative Writer on **matched** per-case source packs, model, transport/config, and planned samples. Keep model-3-Flash-Preview historical 83 separate.
2. Use only canonical shared quota controls, hard per-run cap, private storage; no automatic triggers, API before explicit approval, or plaintext public artifacts.
3. Blind assess 100-point editorial rubric, source fidelity and effective total cost per accepted manuscript; log failures as failures.
4. Go/no-go by repeated independent quality evidence, no ungrounded causality.

## P3 — review boundary and optional integration (separate MERGE GO + release GO)

1. Independent factual claim matching, surgical corrections, independent editorial review. Keep existing Evidence/Fact/Reader/Publication Gates and their thresholds unchanged.
2. Build opt-in validation-only adapter without changing default `classic` or V2 Shadow.
3. Test fail-closed for any missing/unverified evidence, wrong origin, malformed response, persistence attempt, or reviewer rejection.
4. Shadow test, stakeholder approval, then separately consider production release.

## Rollback and stop rules

- During P0–P2: discard development branch/draft PR; `main` remains baseline (or later independently approved main). Do **not** revert V1/V2.
- During P3: disable the opt-in or revert **only the opt-in adapter's** commits; never force-push/reset main.
- Stop on any observed V1/V2/Classic diff, unauthorized provider call, plaintext output leak, Fact/Evidence/Publication gate relaxation or unexplained score deterioration.
- A GREEN test suite or editorial score never authorizes publishing.
