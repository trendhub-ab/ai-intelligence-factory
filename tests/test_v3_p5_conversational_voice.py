"""P5 conversation-style contract; human judgment remains quality authority."""
from __future__ import annotations

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.prompts import (
    CONVERSATIONAL_VOICE_POLICY,
    build_editorial_bundle_prompt,
    build_editorial_stage_prompts,
    build_persona_only_prompt,
)
from experiments.editorial_engine_v3_phase0.reader_experience_audit import diagnose_case


def _stages(article: str) -> dict[str, str]:
    return {
        "Writer Reaction": "Reaction: 何かがおかしい\nQuestion: どういうこと？",
        "Editorial Discovery": "Evidence Pivot: 仕組み\nDeeper Insight: 条件が違う",
        "Cognitive Shift": (
            "Before View: 第一印象\nAfter View: 条件を見直す\n"
            "What I Now Find Interesting: 条件の不一致"
        ),
        "Persona Article Generation": article,
        "Fact-Safe Review": article,
    }


def test_p5_voice_is_applied_to_both_c_generation_routes_only() -> None:
    case = READY_CASES[1].case
    staged = build_editorial_stage_prompts(case)
    bundled = build_editorial_bundle_prompt(case)
    frozen_b = build_persona_only_prompt(case)

    assert CONVERSATIONAL_VOICE_POLICY in staged["Persona Article Generation"]
    assert CONVERSATIONAL_VOICE_POLICY in bundled
    for name in ("Writer Reaction", "Editorial Discovery", "Cognitive Shift", "Fact-Safe Review"):
        assert CONVERSATIONAL_VOICE_POLICY not in staged[name]
    assert CONVERSATIONAL_VOICE_POLICY not in frozen_b
    # The canonical B SHA is already frozen by test_editorial_engine_v3_phase0.py.
    assert "Writer Reaction" not in frozen_b


def test_p5_voice_is_light_and_playful_without_damaging_evidence_or_neutrality() -> None:
    for prompt in (
        build_editorial_stage_prompts(READY_CASES[1].case)["Persona Article Generation"],
        build_editorial_bundle_prompt(READY_CASES[1].case),
    ):
        for marker in (
            "【P5 会話の温度とテンポ】",
            "友人に面白いAIニュースを話す",
            "説明する前に一緒に不思議がる",
            "短い一文",
            "です・ます",
            "報告書調",
            "中性的",
            "軽いツッコミ",
            "同じフレーズを使い回さない",
            "Evidence / Facts / Sources",
            "架空の体験",
        ):
            assert marker in prompt
        assert "敬語を完全に禁止しない" in prompt
        assert "笑いのためにFactを盛らない" in prompt


def test_p5_office_memo_language_is_diagnostic_not_publication_gate() -> None:
    article = (
        "# 計算の話\n\n"
        "この事例は非常に重要な教訓を残しています。"
        "技術評価を厳しく精査することが求められます。"
    )
    report = diagnose_case(_stages(article))
    assert "overformal_report_tone" in report["review_flags"]
    assert "非常に重要な教訓" in report["overformal_report_phrases"]
    assert "ことが求められます" in report["overformal_report_phrases"]
    assert report["not_a_quality_score"] is True
    assert report["not_publication_authority"] is True


def test_p5_actual_concrete_question_is_not_mistaken_for_formality() -> None:
    article = (
        "# 数式では速い。でも本当に？\n\n"
        "理論上の計算量が小さいのに、実機では遅い。"
        "その理由は定数項の大きさにある。"
        "計算量だけを見ていたら、ここは見落としてしまう。"
    )
    report = diagnose_case(_stages(article))
    assert "overformal_report_tone" not in report["review_flags"]
    assert report["overformal_report_phrases"] == []
