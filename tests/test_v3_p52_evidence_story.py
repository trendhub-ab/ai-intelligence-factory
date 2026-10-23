"""P5.2 regressions grounded in real P5 and P5.1 replay manuscripts.

These are offline prompt and diagnostic assertions, not subjective reader-value
proof or semantic source verification. Do not change frozen A/B or replay cases.
"""
from __future__ import annotations

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.contract import validate_reader_facing_article
from experiments.editorial_engine_v3_phase0.prompts import (
    P5_FINAL_EDITORIAL_POLISH,
    build_editorial_bundle_prompt,
    build_editorial_stage_prompts,
    build_persona_only_prompt,
)
from experiments.editorial_engine_v3_phase0.reader_experience_audit import diagnose_case


def _stages(final: str) -> dict[str, str]:
    return {
        "Writer Reaction": "Question: 条件は何？",
        "Editorial Discovery": "Evidence Pivot: 対象の数字",
        "Cognitive Shift": "After View: 条件のある評価",
        "Persona Article Generation": final,
        "Fact-Safe Review": final,
    }


def test_p52_specific_editorial_contract_stays_short_and_keeps_prior_quality() -> None:
    policy = P5_FINAL_EDITORIAL_POLISH
    for phrase in (
        "過去の自分",
        "思っていた",
        "誰の主張",
        "何の指標",
        "評価条件",
        "仕組み",
        "説明を削ら",
        "入力にない",
        "最初の2〜3文",
        "口語でも根拠は変えない",
    ):
        assert phrase in policy
    assert len(policy) <= 750


def test_p52_contract_in_c_routes_without_mutating_persona_only_b() -> None:
    case = READY_CASES[1].case
    stages = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    assert stages["Persona Article Generation"].count(P5_FINAL_EDITORIAL_POLISH) == 1
    assert stages["Fact-Safe Review"].count(P5_FINAL_EDITORIAL_POLISH) == 1
    assert bundle.count(P5_FINAL_EDITORIAL_POLISH) == 1
    assert P5_FINAL_EDITORIAL_POLISH not in build_persona_only_prompt(case)
    for stage in ("Writer Reaction", "Editorial Discovery", "Cognitive Shift"):
        assert P5_FINAL_EDITORIAL_POLISH not in stages[stage]


def test_p51_observed_unmarked_autobiography_flags_for_human_review() -> None:
    samples = (
        "サイズをあらかじめ選ぶのが当たり前だと思っていた。",
        "説明するより自分でやったほうが早いと思ってきた。",
    )
    for sample in samples:
        text = "# 問い\n\n" + sample + "では、実際の証拠は？"
        diagnosis = diagnose_case(_stages(text))
        assert "possible_fabricated_writer_history" in diagnosis["review_flags"]
        assert any(sample.strip("。") in phrase for phrase in diagnosis["possible_writer_history_phrases"])
        assert diagnosis["not_a_quality_score"] is True
        assert diagnosis["not_publication_authority"] is True
        validate_reader_facing_article(text)


def test_real_topic_mechanism_without_personal_history_is_not_flagged() -> None:
    text = (
        "# サイズを変える技術\n\n"
        "内部ユニットに順位を付けて、使う範囲を変える。"
        "再学習なしで変換できると報告されたが、測定条件は何だろう？"
    )
    diagnosis = diagnose_case(_stages(text))
    assert "possible_fabricated_writer_history" not in diagnosis["review_flags"]
    validate_reader_facing_article(text)
