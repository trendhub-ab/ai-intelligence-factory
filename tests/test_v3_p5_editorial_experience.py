"""P5 provider-free regression contracts: story must be reader-discovered, not narrated."""
from __future__ import annotations

import hashlib

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.prompts import (
    EDITORIAL_EXPERIENCE_POLICY,
    build_editorial_bundle_prompt,
    build_editorial_stage_prompts,
    build_persona_only_prompt,
)
from experiments.editorial_engine_v3_phase0.reader_experience_audit import diagnose_case


def _minimal_stage(final: str) -> dict[str, str]:
    return {
        "Writer Reaction": "Reaction: 仕組みが妙だ\nQuestion: なぜ？",
        "Editorial Discovery": "Evidence Pivot: 仕組み\nDeeper Insight: 条件で違う",
        "Cognitive Shift": (
            "Before View: 直感\nAfter View: 条件を見直す\n"
            "What I Now Find Interesting: 具体的な仕組み"
        ),
        "Persona Article Generation": final,
        "Fact-Safe Review": final,
    }


def test_p5_policy_only_changes_c_generation_not_frozen_a_b() -> None:
    case = READY_CASES[1].case
    staged = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    b = build_persona_only_prompt(case)

    assert EDITORIAL_EXPERIENCE_POLICY in staged["Persona Article Generation"]
    assert EDITORIAL_EXPERIENCE_POLICY in bundle
    for stage in ("Writer Reaction", "Editorial Discovery", "Cognitive Shift", "Fact-Safe Review"):
        assert EDITORIAL_EXPERIENCE_POLICY not in staged[stage]
    assert EDITORIAL_EXPERIENCE_POLICY not in b
    assert hashlib.sha256(b.encode("utf-8")).hexdigest() == hashlib.sha256(build_persona_only_prompt(case).encode("utf-8")).hexdigest()


def test_p5_reader_discovers_before_author_reports_impressions() -> None:
    case = READY_CASES[1].case
    for prompt in (
        build_editorial_stage_prompts(case)["Persona Article Generation"],
        build_editorial_bundle_prompt(case),
    ):
        for marker in (
            "P5 読者が先に発見する",
            "証拠の具体的な仕組み",
            "感想を先に宣言",
            "過去の信念を捏造",
            "同じ事実を言い換えて反復",
            "数字や条件を削らない",
            "一人称「私」は必要な場面だけ",
            "Actionを押し付けない",
            "架空の体験",
        ):
            assert marker in prompt
        assert "『以前の私は〜』を根拠なく挿入しない" in prompt
        assert "『私が特に注目したのは』を見出しの代わりに置かない" in prompt


def test_p5_boilerplate_is_human_review_signal_only() -> None:
    text = (
        "# 試作記事\n\n私が特に注目したのは、新しい技術です。\n\n"
        "ここで私の中で疑問が出てきます。\n\n"
        "この技術は非常に実用的です。"
    )
    result = diagnose_case(_minimal_stage(text))
    assert result["not_a_quality_score"] is True
    assert result["not_publication_authority"] is True
    assert "formulaic_writer_narration" in result["review_flags"]
    assert len(result["formulaic_writer_phrases"]) >= 3
    assert result["human_review_required"] is True


def test_p5_concrete_writer_question_does_not_trigger_formulaic_flag() -> None:
    article = (
        "# ひとつのモデルで、何が変わる？\n\n"
        "重い処理と軽い処理を、同じモデルの中で切り替えられる。"
        "一見矛盾する話だが、使うユニットを調整する仕組みがある。"
        "どこまで精度を残せるかは実際に確かめたい。"
    )
    result = diagnose_case(_minimal_stage(article))
    assert "formulaic_writer_narration" not in result["review_flags"]
    assert result["formulaic_writer_phrases"] == []
