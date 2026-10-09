from types import SimpleNamespace

import pytest

from a_plus_editorial_orchestration import install
from editorial_naturalness import editorial_naturalness_v2_diagnostics
from local_skills.a_plus import build_targeted_naturalness_repair_guidance
from ready_yield_guard import compute_ready_yield_metrics


TEMPLATED_ARTICLE = """
# 生成AIの運用判断

## 何が変わったか
公式発表では、新しい管理機能が追加された。利用条件は段階的に公開されている。
つまり、重要なのは導入判断です。私なら条件を確認して判断します。

## なぜ関係するか
一次情報では、管理者向けの制御範囲が広がった。対象範囲には制約も残る。
つまり、重要なのは導入判断です。私なら条件を確認して判断します。

## どこを見るか
公開資料では、利用可能な地域と権限が限定されている。全利用者への提供とは書かれていない。
つまり、重要なのは導入判断です。私なら条件を確認して判断します。

## 次にすること
現時点では公式資料の条件を照合できる。未確認の範囲は断定できない。
つまり、重要なのは導入判断です。私なら条件を確認して判断します。
""".strip()


VARIED_ARTICLE = """
# 管理機能の更新で確認したいこと

## 先に変化を見る
公式発表で管理者向けの設定項目が増えた。対象は一部の契約に限られる。

## 便利さより境界が大事
設定できる項目は増えたが、公開資料には地域差も書かれている。ここは導入可否より、まず自社契約が対象かを照合したい。
追加作業はその確認後でよい。

## 数字にしにくい制約
今回の資料だけでは全利用者への展開時期までは分からない。分からない部分を埋めず、更新履歴を追う。

## 次の一手
管理画面の変更点と公式の対象条件を一度照合する。合わなければ、いまの運用を変えない。
""".strip()


def _codes(result):
    return {row["code"] for row in result["signals"]}


def test_v2_detects_repeated_section_shape_without_hard_blocking():
    result = editorial_naturalness_v2_diagnostics(TEMPLATED_ARTICLE)

    assert "section_structure_repetition" in _codes(result)
    assert result["repair_required"] is True
    assert result["hard_block"] is False
    assert result["blocking_authority"] == "none"


def test_v2_detects_repeated_conclusion_and_speaker_position():
    result = editorial_naturalness_v2_diagnostics(TEMPLATED_ARTICLE)

    codes = _codes(result)
    assert "uniform_conclusion_cadence" in codes
    assert "speaker_voice_position_repetition" in codes
    assert any(row["severity"] in {"P1", "P2"} for row in result["signals"])


def test_v2_natural_control_never_gains_hard_gate_authority():
    result = editorial_naturalness_v2_diagnostics(VARIED_ARTICLE)

    assert result["hard_block"] is False
    assert result["blocking_authority"] == "none"
    assert not any(row["severity"] == "P1" for row in result["signals"])


def test_targeted_guidance_is_issue_specific_and_preserves_evidence_contract():
    guidance = build_targeted_naturalness_repair_guidance(TEMPLATED_ARTICLE)

    assert "Editorial Naturalness v2" in guidance
    assert "section_structure_repetition" in guidance
    assert "uniform_conclusion_cadence" in guidance
    assert "speaker_voice_position_repetition" in guidance
    assert "Fact / Evidence / Decision" in guidance
    assert "required_qualifiers" in guidance
    assert "新しい事実" in guidance
    assert "情報量" in guidance


def test_advisory_only_or_natural_text_does_not_force_repair_guidance():
    guidance = build_targeted_naturalness_repair_guidance(VARIED_ARTICLE)

    assert guidance == ""


def test_ready_yield_guard_is_metrics_only_and_separates_style_only_loss():
    result = compute_ready_yield_metrics(
        [
            {
                "ready": True,
                "hard_gate_blocked": False,
                "naturalness_repair_attempted": False,
                "naturalness_retry_succeeded": None,
                "style_only_non_ready": False,
            },
            {
                "ready": True,
                "hard_gate_blocked": False,
                "naturalness_repair_attempted": True,
                "naturalness_retry_succeeded": True,
                "style_only_non_ready": False,
            },
            {
                "ready": False,
                "hard_gate_blocked": True,
                "naturalness_repair_attempted": False,
                "naturalness_retry_succeeded": None,
                "style_only_non_ready": False,
            },
            {
                "ready": False,
                "hard_gate_blocked": False,
                "naturalness_repair_attempted": True,
                "naturalness_retry_succeeded": False,
                "style_only_non_ready": True,
            },
        ]
    )

    assert result["total_candidates"] == 4
    assert result["ready_count"] == 2
    assert result["ready_rate"] == pytest.approx(0.5)
    assert result["hard_gate_block_count"] == 1
    assert result["hard_gate_block_rate"] == pytest.approx(0.25)
    assert result["naturalness_repair_count"] == 2
    assert result["naturalness_repair_rate"] == pytest.approx(0.5)
    assert result["naturalness_retry_success_rate"] == pytest.approx(0.5)
    assert result["style_only_non_ready_count"] == 1
    assert result["style_only_non_ready_rate"] == pytest.approx(0.25)
    assert result["blocks_ready"] is False
    assert result["policy"] == "diagnostic_only"


def test_ready_yield_guard_handles_empty_window_without_invented_threshold():
    result = compute_ready_yield_metrics([])

    assert result["total_candidates"] == 0
    assert result["ready_rate"] == 0.0
    assert result["naturalness_retry_success_rate"] == 0.0
    assert result["blocks_ready"] is False
    assert "threshold" not in result


def test_a_plus_injects_targeted_guidance_only_into_existing_quality_retry():
    calls = []

    def original_call(
        prompt,
        repo,
        source_info,
        request_kind="deep_dive",
        request_context="",
        request_origin="new",
    ):
        calls.append((prompt, request_kind))
        return SimpleNamespace(text="ok", candidates=[]), {}

    pipeline = SimpleNamespace(
        build_decision_prompt=lambda *args, **kwargs: "prompt\n【Output Contract｜完成稿のみ】",
        _parse_gemini_response=lambda value, *args, **kwargs: value,
        should_attempt_dynamic_retry=lambda *args, **kwargs: (False, "no_retry"),
        call_gemini_grounded_deep_dive=original_call,
        generate_intelligence_report=lambda *args, **kwargs: None,
    )
    install(pipeline)

    pipeline.call_gemini_grounded_deep_dive(
        TEMPLATED_ARTICLE,
        {},
        {},
        request_kind="quality_retry",
    )
    quality_prompt, quality_kind = calls[-1]
    assert quality_kind == "quality_retry"
    assert "Editorial Naturalness v2" in quality_prompt
    assert "Fact / Evidence / Decision" in quality_prompt

    pipeline.call_gemini_grounded_deep_dive(
        TEMPLATED_ARTICLE,
        {},
        {},
        request_kind="deep_dive",
    )
    normal_prompt, normal_kind = calls[-1]
    assert normal_kind == "deep_dive"
    assert normal_prompt == TEMPLATED_ARTICLE
