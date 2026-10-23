"""Regression tests based on real P5 C drafts, not claims of model quality.

Explicit contrastive style cues should not add facts or contaminate frozen A/B.
Hard rejection is limited to observed bad English filler; broad suspicious
wording is a non-gating editor review cue.
"""
from __future__ import annotations

import pytest

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.contract import validate_reader_facing_article
from experiments.editorial_engine_v3_phase0.prompts import (
    P5_STYLE_CONTRAST_EXAMPLES,
    build_editorial_bundle_prompt,
    build_editorial_stage_prompts,
    build_persona_only_prompt,
)
from experiments.editorial_engine_v3_phase0.reader_experience_audit import diagnose_case


def _stages(final: str) -> dict[str, str]:
    return {
        "Writer Reaction": "Reaction: 理論と実用の差\nQuestion: なぜ遅い？",
        "Editorial Discovery": "Evidence Pivot: 大きな定数項",
        "Cognitive Shift": "Before View: 速そう\nAfter View: 実用できない"
                            "\nWhat I Now Find Interesting: 定数項",
        "Persona Article Generation": final,
        "Fact-Safe Review": final,
    }


def test_short_contrastive_examples_replace_report_and_fake_experience() -> None:
    text = P5_STYLE_CONTRAST_EXAMPLES
    for expected in (
        "【P5 対照例：会話調は具体性でつくる】",
        "私が特に注目したのは",
        "以前から",
        "自分に気づくことがあります",
        "今、私たちが取るべきアクション",
        "計算量のつまみ",
        "架空",
        "Evidence / Facts / Sources",
        "文体だけの見本",
    ):
        assert expected in text
    assert len(text) <= 950
    assert "例文をそのままコピーしない" in text


def test_contrastive_examples_are_only_in_c_article_generation_and_bundle() -> None:
    case = READY_CASES[1].case
    prompts = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    assert prompts["Persona Article Generation"].count(P5_STYLE_CONTRAST_EXAMPLES) == 1
    assert bundle.count(P5_STYLE_CONTRAST_EXAMPLES) == 1
    for stage in ("Writer Reaction", "Editorial Discovery", "Cognitive Shift", "Fact-Safe Review"):
        assert P5_STYLE_CONTRAST_EXAMPLES not in prompts[stage]
    assert P5_STYLE_CONTRAST_EXAMPLES not in build_persona_only_prompt(case)


@pytest.mark.parametrize("article", [
    "# Google連携\n\n既存の作業にClaudeを混ぜてみる dream。",
    "# 連携を試す\n\n導入してみる wow。",
])
def test_c_hard_rejects_observed_dangling_english_filler(article: str) -> None:
    with pytest.raises(ValueError, match="stray English filler"):
        validate_reader_facing_article(article)


def test_exact_supplied_source_quote_does_not_trigger_filler_rejection() -> None:
    article = "# 出典を読む\n\n出典には「混ぜてみる dream。」と書かれている。"
    with pytest.raises(ValueError, match="stray English filler"):
        validate_reader_facing_article(article)
    validate_reader_facing_article(article, source_quotes=("混ぜてみる dream。",))


def test_technical_english_and_real_code_not_blanket_blocked() -> None:
    validate_reader_facing_article("# 計算\n\nPythonで benchmark を実行する。")
    validate_reader_facing_article("# 関数\n\n`echo hello` というコマンドを試す。")
    validate_reader_facing_article("# 外国語\n\n英語の用例では hello と書く。")


def test_editorial_flags_are_non_gating_and_grounded_in_real_failure_phrases() -> None:
    bad = (
        "# ケース\n\n"
        "仕事中、何度もタブを往復している自分に気づくことがあります。"
        "AIを導入するとき、いつも悩むものです。"
        "私が特に注目したのはその実用性。"
        "今、私たちが取るべきアクションは何でしょう。"
        "報告書に混ぜてみる benchmark。"
    )
    diagnostic = diagnose_case(_stages(bad))
    assert "possible_fabricated_lived_experience" in diagnostic["review_flags"]
    assert "possible_unsupported_generalization" in diagnostic["review_flags"]
    assert "consulting_style_action_heading" in diagnostic["review_flags"]
    assert "suspicious_stray_english" in diagnostic["review_flags"]
    assert diagnostic["not_a_quality_score"] is True
    assert diagnostic["not_publication_authority"] is True


def test_evidence_led_casual_question_not_auto_flagged() -> None:
    good = (
        "# 伸び縮みするAI？\n\n"
        "学習済みのTransformerを再学習なしで変換できる。"
        "計算量のつまみを後から付けるような話だ。"
        "内部ユニットを共通の尺度で順位付けする。どう動くの？"
    )
    d = diagnose_case(_stages(good))
    for flag in (
        "possible_fabricated_lived_experience",
        "possible_unsupported_generalization",
        "consulting_style_action_heading",
        "suspicious_stray_english",
    ):
        assert flag not in d["review_flags"]
