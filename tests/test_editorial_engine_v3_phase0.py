from __future__ import annotations

import pytest

from experiments.editorial_engine_v3_phase0.contract import (
    EDITORIAL_STAGES,
    MINIMUM_CASES,
    VARIANTS,
    Phase0Case,
    validate_phase0_cases,
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


def test_c_variant_must_use_full_editorial_process_in_order() -> None:
    case = _case("stages")
    assert case.stages_for("C_EDITORIAL_ENGINE") == EDITORIAL_STAGES
    assert case.stages_for("B_PERSONA_ONLY") == ("Article Writing",)
    assert case.stages_for("A_CURRENT_WRITER") == ("Current Writer",)
