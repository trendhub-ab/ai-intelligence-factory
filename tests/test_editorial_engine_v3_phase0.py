from __future__ import annotations

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


def test_phase0_contract_matches_canonical_spec() -> None:
    assert MINIMUM_CASES == 3
    assert VARIANTS == ("A_CURRENT_WRITER", "B_PERSONA_ONLY", "C_EDITORIAL_ENGINE")
    assert EDITORIAL_STAGES == (
        "Editorial Discovery",
        "Persona Narrative",
        "Article Writing",
        "Editorial Review",
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


def test_persona_only_prompt_does_not_smuggle_editorial_discovery_or_review() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    prompt = prompts.build_persona_only_prompt(_case("persona"))
    assert "17歳" in prompt
    assert "外部Fact" in prompt
    assert "Editorial Discovery" not in prompt
    assert "Editorial Review" not in prompt


def test_editorial_engine_prompts_have_four_explicit_stages_and_no_external_fact_rule() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    stages = prompts.build_editorial_stage_prompts(_case("editorial"))
    assert tuple(stages) == EDITORIAL_STAGES
    assert all("外部Fact" in value for value in stages.values())
    assert "Surface" in stages["Editorial Discovery"]
    assert "認識変化" in stages["Persona Narrative"]
    assert "完成稿" in stages["Article Writing"]
    assert "Evidence / Fact" in stages["Editorial Review"]


def test_article_writing_and_review_must_preserve_discovery_and_persona_signal() -> None:
    prompts = _module("experiments.editorial_engine_v3_phase0.prompts")
    stages = prompts.build_editorial_stage_prompts(_case("recognition-preservation"))
    writing = stages["Article Writing"]
    review = stages["Editorial Review"]
    bundle = prompts.build_editorial_bundle_prompt(_case("recognition-preservation"))

    required = (
        "Initial Reaction",
        "Question",
        "Evidence Shift",
        "Deeper Insight",
        "Persona Narrative",
        "無難な解説文",
        "削除しない",
    )
    for marker in required:
        assert marker in writing
        assert marker in review
        assert marker in bundle


def test_blind_package_contains_only_opaque_labels_and_keeps_mapping_separate() -> None:
    runner = _module("experiments.editorial_engine_v3_phase0.runner")
    outputs = dict(zip(VARIANTS, ("first candidate", "second candidate", "third candidate"), strict=True))
    package, mapping = runner.build_blind_package("case-x", outputs)
    serialized_package = json.dumps(package, ensure_ascii=False)
    assert all(variant not in serialized_package for variant in VARIANTS)
    assert set(mapping.values()) == set(VARIANTS)
    assert {row["label"] for row in package["candidates"]} == set(mapping)
