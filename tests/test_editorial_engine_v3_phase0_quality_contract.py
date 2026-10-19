from __future__ import annotations

from experiments.editorial_engine_v3_phase0.contract import Phase0Case
from experiments.editorial_engine_v3_phase0.prompts import (
    build_editorial_bundle_prompt,
    build_editorial_stage_prompts,
)


def _case() -> Phase0Case:
    return Phase0Case(
        case_id="quality-contract",
        title="Quality contract fixture",
        evidence=("evidence-1", "evidence-2"),
        facts=("fact-1", "fact-2"),
        sources=("https://example.com/source",),
        target_reader="経営・企画担当者",
    )


def test_editorial_plan_requires_theme_specific_non_template_narrative_path() -> None:
    case = _case()
    stages = build_editorial_stage_prompts(case)
    discovery = stages["Editorial Discovery"]
    bundle = build_editorial_bundle_prompt(case)

    for prompt in (discovery, bundle):
        for marker in (
            "Narrative Path",
            "構成順は固定しない",
            "同じ骨格",
            "導入・見出し・段落順",
        ):
            assert marker in prompt


def test_final_article_must_not_serialize_planning_fields_in_fixed_order() -> None:
    case = _case()
    stages = build_editorial_stage_prompts(case)
    article = stages["Persona Article Generation"]
    bundle = build_editorial_bundle_prompt(case)

    for prompt in (article, bundle):
        assert "Reaction→Question→before→after→What I Now Find Interesting→判断" in prompt
        assert "この順序をなぞらない" in prompt


def test_fact_safe_review_preserves_input_strength_not_only_fact_presence() -> None:
    case = _case()
    stages = build_editorial_stage_prompts(case)
    review = stages["Fact-Safe Review"]
    bundle = build_editorial_bundle_prompt(case)

    for prompt in (review, bundle):
        for marker in (
            "入力の強さを保存",
            "低減に寄与→直結",
            "手間が省け→なくす",
            "再学習不要→再学習は膨大なコスト",
        ):
            assert marker in prompt


def test_fact_safe_review_audits_background_framing_before_returning_unchanged() -> None:
    case = _case()
    stages = build_editorial_stage_prompts(case)
    review = stages["Fact-Safe Review"]
    bundle = build_editorial_bundle_prompt(case)

    for prompt in (review, bundle):
        for marker in (
            "unchanged判定を先に置かない",
            "導入・背景説明も監査対象",
            "一般的だった",
            "通常は〜が必要",
            "過去の投資を無駄にするリスク",
        ):
            assert marker in prompt


def test_c_voice_contract_keeps_gender_neutral_first_person_and_evidence_boundary() -> None:
    case = _case()
    article = build_editorial_stage_prompts(case)["Persona Article Generation"]
    bundle = build_editorial_bundle_prompt(case)

    for prompt in (article, bundle):
        for marker in (
            "17歳",
            "一人称",
            "中性的",
            "素朴な疑問",
            "若者言葉",
            "Writer Question",
            "Evidence / Facts / Sources",
            "架空",
            "私",
        ):
            assert marker in prompt
        assert "女性的な語尾" in prompt
        assert "男性的な語尾" in prompt
        assert "若者言葉は禁止" not in prompt
        assert "一人称単数は自然なら使ってよいが" not in prompt


def test_p1_editorial_quality_does_not_force_fake_personal_reactions() -> None:
    case = _case()
    stages = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    for prompt in (stages["Persona Article Generation"], bundle):
        assert "架空の体験談を作らない" in prompt
        assert "一人称を毎記事の冒頭に強制しない" in prompt
        assert "驚きを説明せず、Evidenceの具体性で読者に発見させる" in prompt
        assert "同じ感情の型を複数記事に使い回さない" in prompt
        assert "読者にとっての判断材料を具体的に示す" in prompt


def test_p2_reader_facing_prompts_isolate_internal_decision_labels() -> None:
    case = _case()
    stages = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    for prompt in (stages["Persona Article Generation"], stages["Fact-Safe Review"], bundle):
        assert "TRY / WATCH / PASS / AVOID" in prompt
        assert "内部メタデータ" in prompt
        assert "読者向け" in prompt
        assert "構造化判断データ" in prompt
        assert "引用" in prompt


def test_p2_voice_and_plain_language_keep_fact_boundary() -> None:
    case = _case()
    stages = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    for prompt in (stages["Persona Article Generation"], bundle):
        for marker in ("一人称「私」", "経験を捏造しない", "専門用語", "日常語", "短い段落", "Evidence", "同じ型を使い回さない"):
            assert marker in prompt
    for prompt in (stages["Fact-Safe Review"], bundle):
        assert "Fact" in prompt
        assert "Evidence / Facts / Sources" in prompt
