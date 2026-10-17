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
