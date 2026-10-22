"""Offline tests: V3 quality signal visibility, not automated 'interesting' GO."""
from __future__ import annotations

import json
from pathlib import Path

from experiments.editorial_engine_v3_phase0.reader_experience_audit import (
    audit_state,
    diagnose_case,
)


def _stages(*, flattened: bool = False) -> dict[str, str]:
    draft = (
        "# AIに忘れさせるには\n\n"
        "私は最初、同じAIなら同じ処理で忘れられると思った。\n\n"
        "同じAIなのに削除後の正解が違うのはなぜ？\n\n"
        "違うデータで学んだ結果なら、削除後に戻る先が違う。そこが面白い。"
    )
    flat = "# AIに忘れさせるには\n\n忘却処理には課題があります。技術の評価が必要です。"
    return {
        "Writer Reaction": (
            "Reaction: 同じモデルでも忘却は異なる？\n"
            "Question: 同じAIなのに削除後の正解が違うのはなぜ？\n"
        ),
        "Editorial Discovery": (
            "Evidence Pivot: 同じAIなのに削除後の正解が違う\n"
            "Deeper Insight: 削除後の正解は学習履歴に依存する\n"
        ),
        "Cognitive Shift": (
            "Before View: 同じAIなら同じ削除をする\n"
            "After View: 違うデータで学んだ結果なら削除後に戻る先が違う\n"
            "What I Now Find Interesting: 戻る先を知るために履歴が要る\n"
        ),
        "Persona Article Generation": draft,
        "Fact-Safe Review": flat if flattened else draft,
    }


def test_p3_discovery_is_in_both_live_c_prompts_without_touching_frozen_b() -> None:
    from experiments.editorial_engine_v3_phase0.cases import READY_CASES
    from experiments.editorial_engine_v3_phase0.prompts import (
        READER_DISCOVERY_SCENE,
        build_editorial_bundle_prompt,
        build_editorial_stage_prompts,
        build_persona_only_prompt,
    )
    case = READY_CASES[1].case
    staged = build_editorial_stage_prompts(case)["Persona Article Generation"]
    bundled = build_editorial_bundle_prompt(case)
    frozen_b = build_persona_only_prompt(case)
    for text in (staged, bundled):
        assert READER_DISCOVERY_SCENE in text
        assert "読者自身がEvidenceの仕組み" in text
        assert "架空の利用体験" in text
        assert "固定文字数" in text
    assert READER_DISCOVERY_SCENE not in frozen_b


def test_p3_diagnostic_module_is_classified_experiment_infrastructure() -> None:
    import member_customer_surface_contract as contract
    assert "experiments/editorial_engine_v3_phase0/reader_experience_audit.py" in contract.NON_MEMBER_MODULES


def test_healthy_article_retains_writer_question_and_evidence_change() -> None:
    result = diagnose_case(_stages())
    assert result["writer_voice_visible"] is True
    assert result["question_punctuation_visible"] is True
    assert result["planning_anchor_status"]["question"] == "surface_present"
    assert result["planning_anchor_status"]["evidence_pivot"] == "surface_present"
    assert "first_person_removed_in_fact_review" not in result["review_flags"]
    assert result["not_publication_authority"] is True


def test_flattened_review_is_flagged_but_does_not_pretend_to_grade_interest() -> None:
    result = diagnose_case(_stages(flattened=True))
    assert result["review_stage_changed_prose"] is True
    assert "first_person_removed_in_fact_review" in result["review_flags"]
    assert "writer_question_not_visible" in result["review_flags"]
    assert "question_surface_not_retained" in result["review_flags"]
    assert result["human_review_required"] is True


def test_loss_stage_attributes_missing_question_to_article_generation() -> None:
    stages = _stages()
    stages["Persona Article Generation"] = (
        "# AIに忘れさせるには\n\n私は技術の仕組みを理解しました。"
    )
    stages["Fact-Safe Review"] = stages["Persona Article Generation"]
    result = diagnose_case(stages)
    assert result["possible_loss_stage"]["question"] == "possible_loss_during_article_generation"
    assert "question_possible_loss_in_article_generation" in result["review_flags"]
    assert "question_possible_loss_in_fact_safe_review" not in result["review_flags"]


def test_loss_stage_attributes_fact_review_flattening_only_when_draft_retained() -> None:
    result = diagnose_case(_stages(flattened=True))
    assert result["planning_anchor_in_article_generation"]["question"] == "surface_present"
    assert result["possible_loss_stage"]["question"] == "possible_loss_during_fact_safe_review"
    assert "question_possible_loss_in_fact_safe_review" in result["review_flags"]


def test_generic_v1_intro_is_a_review_flag_not_a_hard_gate() -> None:
    stages = _stages()
    stages["Fact-Safe Review"] = (
        "# 忘却\n\n## どんな内容？\n説明です。\n\n"
        "## なぜ重要？\n解説です。\n\n## 結論は？\nまとめです。"
    )
    result = diagnose_case(stages)
    assert "fixed_v1_summary_intro" in result["review_flags"]
    assert "human_review_required" in result


def test_absent_or_paraphrased_planning_labels_do_not_become_false_success() -> None:
    stages = _stages()
    stages["Writer Reaction"] = "短い反応だけ"
    result = diagnose_case(stages)
    assert result["planning_anchor_status"]["question"] == "not_evaluable"
    assert result["not_a_quality_score"] is True


def test_c_only_diagnostic_never_exposes_stale_incomplete_cases() -> None:
    good = _stages()
    state = {
        "mode": "C_ONLY_REFINEMENT",
        "c_completed_case_ids": ["a"],
        "cases": [
            {"case_id":"a", "editorial_stage_outputs":good,
             "outputs":{"C_EDITORIAL_ENGINE":good["Fact-Safe Review"]}},
            {"case_id":"b", "editorial_stage_outputs":_stages(),
             "outputs":{"C_EDITORIAL_ENGINE":good["Fact-Safe Review"]}},
        ],
    }
    report = audit_state(state)
    assert [case["case_id"] for case in report["cases"]] == ["a"]
    assert report["provider_calls"] == 0
    assert report["human_blind_acceptance_still_required"] is True


def test_mismatched_c_output_is_excluded_from_diagnostics() -> None:
    good = _stages()
    state = {
        "mode": "FULL",
        "cases": [{"case_id":"a","editorial_stage_outputs":good,
                   "outputs":{"C_EDITORIAL_ENGINE":"# Unrelated\n\nDifferent body"}}],
    }
    assert audit_state(state)["cases"] == []


def test_live_writes_diagnostics_alongside_blind_artifacts(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0.live import _write_evaluation_artifacts
    stages = _stages()
    state = {
        "mode":"FULL", "selected_model":"fixture-no-provider",
        "cases":[{"case_id":"a","editorial_stage_outputs":stages,
                  "outputs":{"C_EDITORIAL_ENGINE":stages["Fact-Safe Review"]}}],
        "blind_packages":[], "blind_mapping":{},
    }
    _write_evaluation_artifacts(tmp_path, state)
    report = json.loads((tmp_path / "c_reader_experience_diagnostics.json").read_text(encoding="utf-8"))
    assert len(report["cases"]) == 1
    assert report["cases"][0]["diagnostic"]["writer_voice_visible"] is True
    assert report["provider_calls"] == 0
    assert "not_a_quality_score" in report["cases"][0]["diagnostic"]
