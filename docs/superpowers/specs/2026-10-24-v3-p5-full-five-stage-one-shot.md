# AIIF V3 P5 — Original Five-Stage Writer × Production ONE-SHOT

Status: **Implementation draft, not yet Production authorized**. Baseline: proven P5 PR #852 SHA `95016a65701979063f56130bf181bca831661f5d`. Draft integration PR #860.

## Goal and owner constraints

- The ONLY P5 reference is the original 83-point subjective-editorial benchmark. This number is not guaranteed on new articles or against Production prompts.
- Reproduce P5's actual five-stage creative process, **not** an approximation based on six separate style statements.
- Keep LocalSkills as Evidence/Decision/Action owner, Gemini as writer and all unchanged Evidence/Fact/Reader/Publication Gates as authoritative.
- Reader-visible structure: front `どんな内容？`, `なぜ重要？`, `結論は？`, `元情報`; then P5 writer's original article; keep `Sources / Evidence` at end even if primary reference appears twice. User explicitly approved current source attribution in both locations.
- Preserve other styles/default and rollback; avoid unnecessary Gemini calls, failures fail closed.
- Development of P5 itself remains open; the historical P5 reference is not permission to freeze all improvements indefinitely.

## Architecture

1. ONE-SHOT workflow_dispatch `editorial_style=v3_p5` is optional, `classic` remains default. Until actual full article human verification, P5 is permitted only in bounded validation modes: `article_validation`, `local_skills_production_validation`, `production_e2e_validation`. `full` and other modes fail in the initial safety step; no note publishing/Ready fan-out from experimental P5.
2. Canonical `pipeline.build_decision_prompt` + existing A+ LocalSkills prewrite unchanged. First call uses canonical management shaping to produce mandatory eight MANAGEMENT DATA fields and initial draft. The draft is **not** published.
3. Extra **one** provider call, via same `call_gemini_grounded_deep_dive` route, `deep_dive` budget, existing health-aware pool/quota/per-run request/503 owner. This call uses original P5 `build_editorial_bundle_prompt` and exactly five deliverables:
   - Writer Reaction
   - Editorial Discovery
   - Cognitive Shift
   - Persona Article Generation
   - Fact-Safe Review
4. Source input from verified `source_info.verification_context` / `context` and structured evidence, required qualifiers, primary source, plus existing canonical Decision/Action and LocalSkills prewrite constraints. First-call management is guidance for Decision/Action, **not newly promoted evidence**.
5. Strict parser: exactly five non-empty keys, full H1 Japanese article in both draft and final, source-aware boundary and no leaked internal verdict / mixed-script anomalies.
6. Convert **Fact-Safe Review final only** to canonical `SECTION_SPLIT_TOKEN` article, append to **unchanged** MANAGEMENT DATA, parse via existing Production parser, then proceed through preexisting all Gates, source persistence, note formatting, return logic.
7. Fail closed on missing verified sources, incomplete management, malformed bundle, missing stages, empty manuscript, any rejected final form or provider errors. Never substitute first-pass generic draft as a successful P5 output.
8. Extra call consumes an additional logical Deep Dive budget (2 per initial manuscript, plus potential existing Quality Retry cost). No new keys/credentials, no retry owner outside the canonical provider route, no hidden API/model calls. The P5 five stages are **one bundled generation**, not five API calls.

## Evidence / constraints

- Original five-stage prompt and validator modules ported with only relative import replacement from commit above to `local_skills/v3_p5_prompts.py` and `local_skills/v3_p5_contract.py`. Baseline is static **for comparison**, not a restriction on future tracked P5 revisions.
- `local_skills/v3_p5_one_shot.py`: provider-free orchestration and validation; real API lives only in existing provider client.
- `a_plus_editorial_orchestration.py`: optional selected style at established stage; not a new runtime layer/order.
- `content_generation_protocol.py`: first management call uses original `classic` style shaping for `v3_p5`; the true voice happens in second five-stage call.
- `.github/workflows/daily-one-shot.yml`: option user-selectable, default classic and explicit validation-only guard, retained Gemini quota group.
- Existing two-source A/B using six cue-only adapter scored weakly; **do not present this as a measurement of full five-stage P5**.
- CI focused first proof: `40044192245` / 7 tests PASS. Full pytest/repository Guards required before merge. New live human blind comparison on identical official source + Gate proof separately required before FULL enable.

## Go/no-go and rollback

- Before `MERGE GO`, hold PR as DRAFT, main unchanged, no Daily dispatch.
- In validation, reject Fact/Evidence/Publication faults unconditionally regardless of writer/editorial score; compare curiosity, discovery, warmth, readability, reader completion incentive with P5 baseline **without assigning speculative 90 points**.
- Rollback simply omits `v3_p5` selection and uses `classic` (unchanged one-call route).
