"""Provider-free P5 fidelity regressions from three real 2026-10-23 C drafts.

These are prompt/diagnostic contracts, not a claim of semantic fact checking,
human delight, or permission to publish. Frozen Phase 0 cases and A/B stay fixed.
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


def _stages(text: str) -> dict[str, str]:
    return {
        "Writer Reaction": "Question: この数字はどの条件？",
        "Editorial Discovery": "Evidence Pivot: 評価対象と条件",
        "Cognitive Shift": "After View: 条件つきの結果",
        "Persona Article Generation": text,
        "Fact-Safe Review": text,
    }


def test_p5_scope_rule_keeps_attribution_and_qualifiers() -> None:
    rule = P5_FINAL_EDITORIAL_POLISH
    for term in (
        "発信主体",
        "対象モデル",
        "データセット",
        "評価条件",
        "推定",
        "与えられた入力",
        "事実を足さない",
        "意外性",
    ):
        assert term in rule
    assert len(rule) < 1000


def test_p5_scope_rule_only_changes_c_and_not_frozen_ab() -> None:
    case = READY_CASES[1].case
    staged = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    assert staged["Persona Article Generation"].count(P5_FINAL_EDITORIAL_POLISH) == 1
    assert staged["Fact-Safe Review"].count(P5_FINAL_EDITORIAL_POLISH) == 1
    assert bundle.count(P5_FINAL_EDITORIAL_POLISH) == 1
    for stage in ("Writer Reaction", "Editorial Discovery", "Cognitive Shift"):
        assert P5_FINAL_EDITORIAL_POLISH not in staged[stage]
    assert P5_FINAL_EDITORIAL_POLISH not in build_persona_only_prompt(case)


def test_recent_p5_formulas_are_editorial_flags_not_publication_gates() -> None:
    text = (
        "# 新しい見方\n\n皆さんはどう感じますか？"
        "私がここで一番気になったのは、この数値です。"
        "でも、ちょっと待ってください。"
        "想定条件を見てから判断したい。"
    )
    diagnosis = diagnose_case(_stages(text))
    assert "formulaic_writer_narration" in diagnosis["review_flags"]
    assert "皆さんはどう感じますか" in diagnosis["formulaic_writer_phrases"]
    assert "私がここで一番気になったのは" in diagnosis["formulaic_writer_phrases"]
    assert diagnosis["not_a_quality_score"] is True
    assert diagnosis["not_publication_authority"] is True
    # Review flags must never become arbitrary hard rejection of natural Japanese.
    validate_reader_facing_article(text)


def test_concrete_topic_question_is_not_mislabeled_formulaic() -> None:
    text = (
        "# 計算量が変わる？\n\n50%削ったときの0.8%は、"
        "どのモデルの何の精度なのだろう？"
        "対象と測定方法を確かめてから考えたい。"
    )
    diagnosis = diagnose_case(_stages(text))
    assert not diagnosis["formulaic_writer_phrases"]
    validate_reader_facing_article(text)
