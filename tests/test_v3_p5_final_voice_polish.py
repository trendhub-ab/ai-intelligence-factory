"""Provider-free P5 polish regression: editorial warmth with evidence boundaries.

These lexical cues are not objective interest scores or replacements for human review.
A narrow mixed-script typo is a fail-closed format defect only for experimental C.
"""
from __future__ import annotations

import pytest

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.contract import validate_reader_facing_article
from experiments.editorial_engine_v3_phase0.prompts import (
    P5_FINAL_EDITORIAL_POLISH,
    build_editorial_stage_prompts,
    build_editorial_bundle_prompt,
    build_persona_only_prompt,
)
from experiments.editorial_engine_v3_phase0.reader_experience_audit import diagnose_case


def _stages(article: str) -> dict[str, str]:
    return {
        "Writer Reaction": "Reaction: 面白い違いがある\nQuestion: どうしてこうなる？",
        "Editorial Discovery": "Evidence Pivot: 条件が異なる\nDeeper Insight: 仕組みが違う",
        "Cognitive Shift": (
            "Before View: 最初の仮説\nAfter View: 条件で変わる\n"
            "What I Now Find Interesting: 意外な条件差"
        ),
        "Persona Article Generation": article,
        "Fact-Safe Review": article,
    }


def test_p5_final_polish_in_both_c_routes_not_frozen_b() -> None:
    case = READY_CASES[1].case
    staged = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    b = build_persona_only_prompt(case)

    assert P5_FINAL_EDITORIAL_POLISH in staged["Persona Article Generation"]
    assert P5_FINAL_EDITORIAL_POLISH in staged["Fact-Safe Review"]
    assert P5_FINAL_EDITORIAL_POLISH in bundle
    assert P5_FINAL_EDITORIAL_POLISH not in b
    assert P5_FINAL_EDITORIAL_POLISH not in staged["Writer Reaction"]
    assert P5_FINAL_EDITORIAL_POLISH not in staged["Editorial Discovery"]
    assert P5_FINAL_EDITORIAL_POLISH not in staged["Cognitive Shift"]


def test_p5_final_polish_avoids_invented_histories_generalities_and_slogan_endings() -> None:
    text = build_editorial_bundle_prompt(READY_CASES[1].case)
    for marker in (
        "読者がつい続きを読みたくなる",
        "最初の2〜3文",
        "架空の過去",
        "一般的だった",
        "いつも",
        "定着しないケース",
        "業界標準になる",
        "追加コストなし",
        "根拠のない普遍化",
        "同じ感情の型",
        "中性的",
        "Evidence / Facts / Sources",
        "Fact-Safe Review",
    ):
        assert marker in text
    assert "無理な驚きや連続した疑問文を強制しない" in text
    assert "誤字の自動修復で事実を変えない" in text


@pytest.mark.parametrize("body", [
    "これは実務의スピードを変える。",
    "この업務では条件が違う。",
    "導入すると作業의精度が上がる。",
])
def test_c_rejects_accidental_hangul_inside_japanese_words(body: str) -> None:
    with pytest.raises(ValueError, match="mixed-script"):
        validate_reader_facing_article("# 確認\n\n" + body)


def test_c_respects_exact_source_quotation_exception() -> None:
    article = "# 引用を確認\n\n原文では「実務의スピード」と記載されている。"
    with pytest.raises(ValueError, match="mixed-script"):
        validate_reader_facing_article(article)
    validate_reader_facing_article(article, source_quotes=("実務의スピード",))


def test_not_blanket_ban_on_other_languages_or_unicode() -> None:
    validate_reader_facing_article("# 外国語の引用\n\n韓国語の単語 한글 を紹介する。")
    validate_reader_facing_article("# 計算量の話\n\nこの条件だと計算量が半分になる。")


def test_p5_rejects_bad_unicode_without_rewriting_other_text() -> None:
    article = "# 検証\n\n実務의スピードが変わる。"
    with pytest.raises(ValueError):
        validate_reader_facing_article(article)
    assert "의" in article


def test_p5_editorial_cues_are_non_gating_only() -> None:
    article = (
        "# FFTの話\n\n"
        "以前は理論上の証明さえあれば進歩だと思っていた。"
        "新技術はこれからのスタンダードになる予感がする。"
        "試さない手はありません。"
    )
    report = diagnose_case(_stages(article))
    assert "possible_fabricated_writer_history" in report["review_flags"]
    assert "possible_unsupported_promise" in report["review_flags"]
    assert report["not_a_quality_score"] is True
    assert report["not_publication_authority"] is True
    assert report["human_review_required"] is True


def test_p5_good_specific_explanation_does_not_trigger_new_editorial_cues() -> None:
    article = (
        "# 速いはずが遅い？\n\n"
        "定数項が10の100乗規模なら、理論上の計算量が小さくても"
        "今のハードウェアでは実用的ではない。数式と実効速度は別の話だった。"
    )
    flags = diagnose_case(_stages(article))["review_flags"]
    assert "possible_fabricated_writer_history" not in flags
    assert "possible_unsupported_promise" not in flags
