from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json

import pytest

from experiments.editorial_engine_v3_phase0.contract import (
    EDITORIAL_STAGES,
    MINIMUM_CASES,
    VARIANTS,
    Phase0Case,
    validate_phase0_cases,
)


EXPECTED_READY_CASE_IDS = (
    "3f8479ff-dca9-8146-b90d-df1fc42c40ef",
    "3fa479ff-dca9-8194-a493-cb3a0d2b3a36",
    "3f3479ff-dca9-8153-a62e-d3768adb3160",
)


def _case(case_id: str) -> Phase0Case:
    return Phase0Case(
        case_id=case_id,
        title=f"Ready article {case_id}",
        evidence=("evidence-1", "evidence-2"),
        facts=("fact-1", "fact-2"),
        sources=("https://example.com/source-1",),
        target_reader="経営・企画担当者",
    )


def _module(name: str):
    spec = importlib.util.find_spec(name)
    assert spec is not None, f"Phase 0 module is required: {name}"
    return importlib.import_module(name)


def test_phase0_contract_matches_reaction_first_spec() -> None:
    assert MINIMUM_CASES == 3
    assert VARIANTS == ("A_CURRENT_WRITER", "B_PERSONA_ONLY", "C_EDITORIAL_ENGINE")
    assert EDITORIAL_STAGES == (
        "Writer Reaction",
        "Editorial Discovery",
        "Cognitive Shift",
        "Persona Article Generation",
        "Fact-Safe Review",
    )


def test_phase0_requires_at_least_three_real_ready_cases() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        validate_phase0_cases((_case("one"), _case("two")))


def test_case_payload_is_shared_immutably_across_variants() -> None:
    case = _case("shared")
    payload_a = case.shared_payload("A_CURRENT_WRITER")
    payload_b = case.shared_payload("B_PERSONA_ONLY")
    payload_c = case.shared_payload("C_EDITORIAL_ENGINE")

    for field in ("evidence", "facts", "sources", "target_reader"):
        assert payload_a[field] == payload_b[field] == payload_c[field]

    assert payload_a["variant"] != payload_b["variant"] != payload_c["variant"]


def test_external_fact_addition_is_fail_closed() -> None:
    case = _case("facts")
    with pytest.raises(ValueError, match="external facts"):
        case.assert_generated_facts_are_allowed(("fact-1", "invented-fact"))


def test_variant_stage_contract_matches_spec() -> None:
    case = _case("stages")
    assert case.stages_for("C_EDITORIAL_ENGINE") == EDITORIAL_STAGES
    assert case.stages_for("B_PERSONA_ONLY") == ("Persona Narrative", "Article Writing")
    assert case.stages_for("A_CURRENT_WRITER") == ("Current Writer",)


def test_three_real_ready_cases_are_frozen_without_existing_article_prose() -> None:
    cases_module = _module("experiments.editorial_engine_v3_phase0.cases")
    cases = tuple(cases_module.READY_CASES)
    assert tuple(item.case.case_id for item in cases) == EXPECTED_READY_CASE_IDS
    assert len({item.theme for item in cases}) == 3
    assert all(item.case.evidence and item.case.facts and item.case.sources for item in cases)
    assert all(item.case.target_reader for item in cases)
    forbidden = {"article", "article_body", "body", "clean_manuscript", "existing_article", "note_draft", "previous_article"}
    for item in cases:
        assert forbidden.isdisjoint(item.management)
        assert item.ready_status == "Ready"


def test_current_writer_snapshot_uses_production_adapter_and_shared_structured_input() -> None:
    cases_module = _module("experiments.editorial_engine_v3_phase0.cases")
    runner = _module("experiments.editorial_engine_v3_phase0.runner")
    item = cases_module.READY_CASES[0]
    snapshot = runner.build_current_writer_snapshot(item)
    assert snapshot["source_summary"] == item.management["source_summary_text"]
    assert snapshot["what"] == item.management["what_text"]
    assert snapshot["why_important"] == item.management["why_important_text"]
    assert snapshot["decision"] == item.management["decision_text"]
    assert snapshot["decision_reason"] == item.management["decision_reason_text"]
    assert snapshot["action"] == item.management["action_text"]
    assert snapshot["evidence_urls"] == list(item.case.sources)


def test_persona_only_prompt_does_not_smuggle_reaction_first_editorial_stages() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    prompt = prompts.build_persona_only_prompt(_case("persona"))
    assert "17歳" in prompt
    assert "外部Fact" in prompt
    assert "Writer Reaction" not in prompt
    assert "Editorial Discovery" not in prompt
    assert "Fact-Safe Review" not in prompt


def test_persona_only_baseline_stays_byte_frozen() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    baseline = prompts.build_persona_only_prompt(_case("persona"))
    assert hashlib.sha256(baseline.encode("utf-8")).hexdigest() == (
        "49131f6f19b1df3d183610573cfc2806a26e8096bb2b2a07dbb166425865c315"
    )
    assert "若者言葉、過剰な感嘆符、絵文字、架空の実体験は使わない" in baseline
    assert "男女を推測できない中性的" not in baseline


def test_reaction_first_stage_prompts_have_five_explicit_stages_and_fact_boundary() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    stages = prompts.build_editorial_stage_prompts(_case("editorial"))
    assert tuple(stages) == EDITORIAL_STAGES
    assert all("外部Fact" in value for value in stages.values())

    reaction = stages["Writer Reaction"]
    for marker in ("Reaction", "Curiosity", "Question", "Future Imagination", "Emotion Intensity"):
        assert marker in reaction

    discovery = stages["Editorial Discovery"]
    for marker in ("Surface", "Interesting Tension", "Evidence Pivot", "Deeper Insight", "Editorial Thesis"):
        assert marker in discovery

    shift = stages["Cognitive Shift"]
    for marker in ("Before View", "Evidence Encounter", "After View", "What I Now Find Interesting"):
        assert marker in shift
    assert "固定" in shift

    article = stages["Persona Article Generation"]
    for marker in ("Writer Reaction", "Question", "Cognitive Shift", "discovery", "成人ビジネス"):
        assert marker in article

    review = stages["Fact-Safe Review"]
    for marker in ("変更しない", "最小", "一人称", "好奇心", "specific question", "Future Imagination"):
        assert marker in review


def test_persona_article_generation_explicitly_preserves_writer_owned_anchors() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    article = prompts.build_editorial_stage_prompts(_case("preservation"))["Persona Article Generation"]

    for marker in (
        "writer-owned anchor",
        "Writer Question",
        "before→after",
        "What I Now Find Interesting",
        "私たちは〜",
        "疑問が生じます",
        "〜ではないでしょうか",
        "置換しない",
    ):
        assert marker in article


def test_fact_safe_review_rejects_true_but_unstated_and_stronger_assertions() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    review = prompts.build_editorial_stage_prompts(_case("strict-facts"))["Fact-Safe Review"]

    for marker in (
        "true-but-unstated",
        "stronger-than-input",
        "unsupported causal claim",
        "unsupported generalization",
        "Evidence / Facts / Sources",
    ):
        assert marker in review


def test_reaction_first_bundle_requires_exact_stage_keys_and_preservation_policy() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    bundle = prompts.build_editorial_bundle_prompt(_case("bundle"))

    for stage in EDITORIAL_STAGES:
        assert stage in bundle
    for marker in (
        "Reaction",
        "Curiosity",
        "Question",
        "Future Imagination",
        "Emotion Intensity",
        "Before View",
        "Evidence Encounter",
        "After View",
        "What I Now Find Interesting",
        "外部Fact",
        "変更しない",
        "最小",
    ):
        assert marker in bundle

    assert "Persona Narrative" not in bundle
    assert "Editorial Review" not in bundle


def test_reaction_first_bundle_carries_persona_anchors_and_strict_fact_review_into_one_call() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    bundle = prompts.build_editorial_bundle_prompt(_case("bundle-preservation"))

    for marker in (
        "writer-owned anchor",
        "Writer Question",
        "before→after",
        "私たちは〜",
        "疑問が生じます",
        "〜ではないでしょうか",
        "true-but-unstated",
        "stronger-than-input",
        "unsupported causal claim",
        "unsupported generalization",
    ):
        assert marker in bundle


def test_blind_package_contains_only_opaque_labels_and_keeps_mapping_separate() -> None:
    runner = _module("experiments.editorial_engine_v3_phase0.runner")
    outputs = dict(zip(VARIANTS, ("first candidate", "second candidate", "third candidate"), strict=True))
    package, mapping = runner.build_blind_package("case-x", outputs)
    serialized_package = json.dumps(package, ensure_ascii=False)
    assert all(variant not in serialized_package for variant in VARIANTS)
    assert set(mapping.values()) == set(VARIANTS)
    assert {row["label"] for row in package["candidates"]} == set(mapping)


def test_c_only_partial_blind_state_exposes_only_current_completed_cases() -> None:
    live = _module("experiments.editorial_engine_v3_phase0.live")
    completed = list(EXPECTED_READY_CASE_IDS[:2])
    cases = []
    for index, case_id in enumerate(EXPECTED_READY_CASE_IDS):
        cases.append(
            {
                "case_id": case_id,
                "outputs": {
                    "A_CURRENT_WRITER": f"A-{index}",
                    "B_PERSONA_ONLY": f"B-{index}",
                    "C_EDITORIAL_ENGINE": f"C-{index}",
                },
            }
        )
    state = {
        "mode": "C_ONLY_REFINEMENT",
        "c_completed_case_ids": completed,
        "cases": cases,
        "blind_packages": [],
        "blind_mapping": {},
    }

    live._rebuild_blind_state(state)

    assert [package["case_id"] for package in state["blind_packages"]] == completed
    assert set(state["blind_mapping"]) == set(completed)
