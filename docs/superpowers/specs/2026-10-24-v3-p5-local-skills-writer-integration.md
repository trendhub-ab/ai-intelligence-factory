# V3 P5 → LocalSkills/Production Writer adapter (2026-10-24)

Status: **Draft integration, not yet approved for production release, Daily Full, or note delivery**. Baseline `main` `ea9b8ade77d09167d798de32201b40f866a0fd77`.

## Owner-approved objective

Integrate the editorial voice from P5 [PR #852](https://github.com/trendhub-ab/ai-intelligence-factory/pull/852) without further tuning its proven policy, while keeping LocalSkills, Evidence / Fact / Publication Gate and existing Production output schema as the authorities. P5 three-article subjective editorial review mean **83/100**, not proof of 90+, Fact accuracy or publishability. P5.1/P5.2 regressions are archived, never merged.

## Exact implementation and boundaries

- Add `local_skills/v3_p5_writer.py` with **six immutable P5 policy values copied verbatim from P5 commit `95016a65701979063f56130bf181bca831661f5d`**. This file has no network, model calls, credentials or publication.
- In canonical `content_generation_protocol.editorial_style_rules`, opt-in `v3_p5` selects the frozen P5 policy. Existing `classic`, `human_narrative`, `duo_narrative` remain unchanged and all unknown choices still fail closed.
- A+ orchestration already injects LocalSkills `build_prewrite_contract` after the style contract and before the authoritative `【Output Contract｜完成稿のみ】`. This adapter **does not** change A+, factual metadata, evidence sufficiency, provider/call count, parser, deterministic fallback, final publication/Reader gates, delivery or note/Notion.
- Daily ONE-SHOT exposes `v3_p5` as an **explicit opt-in**. `classic` remains default, so an ordinary Daily is **not** switched to P5 merely by merging. Legacy `daily.yml` remains paused; do not restart it automatically.
- **Material limitation:** This is a schema-compatible **P5 Writer policy/voice adapter**, *not* the exact isolated Phase-0 5-stage C model pipeline. The V3 test engine asks for a distinct JSON shape (`Writer Reaction`, `Editorial Discovery`, `Cognitive Shift`, `Persona Article Generation`, `Fact-Safe Review`) and uses a frozen 3-case dataset. Naively reproducing that JSON in Production would break the existing 8-field MANAGEMENT DATA and article parsing. The frozen writer policy is selected for the current one-call Production generator; actual quality must be measured on fresh inputs. **Do not misstate this adaptation as replicating the five-stage V3 engine.**

## Validation plan before MERGE GO

1. Provider-free regression: frozen six policy values; style-router opt-in and legacy unchanged; A+ LocalSkills injected exactly once; output schema unaffected; malformed style fails closed; Daily default unchanged.
2. Full CI pytest and guards; review any conflicts with source/context and management data.
3. Before public Production use, run dedicated `local_skills_production_validation` or controlled no-persistence article validation via `v3_p5`; compare with classic using the same verified source/input, then blind score reader engagement + Gate outcomes. **No Gemini API calls in this PR**.
4. If readability regresses, change adapter interaction/selection, not frozen P5 policies. If gate fails, fail closed. No unsupported automatic quality score claim.
5. Only after explicit owner **MERGE GO** is any merge to main permitted. Separate explicit owner approval before full Daily delivery/Note publication, and check dedupe/quota first.

Risk note: existing Production formatting and management contracts can suppress some of P5's 83-point characteristics; style-contract equivalence does not prove manuscript equivalence. Full experimental five-stage integration, if warranted by blind results, requires separately designed changes and API budget review.
