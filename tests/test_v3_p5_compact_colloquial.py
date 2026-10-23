"""P5: a concise, naturally spoken editorial contract, not extra verbose safety rules."""
from __future__ import annotations

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.prompts import (
    EDITORIAL_EXPERIENCE_POLICY,
    CONVERSATIONAL_VOICE_POLICY,
    P5_FINAL_EDITORIAL_POLISH,
    FACT_SAFE_FULL_MANUSCRIPT_CONTRACT,
    build_editorial_bundle_prompt,
    build_editorial_stage_prompts,
    build_persona_only_prompt,
)


def test_colloquial_voice_is_warm_not_fake_slang_or_formal_report() -> None:
    voice = CONVERSATIONAL_VOICE_POLICY
    for phrase in (
        "もっと砕けた口語調",
        "だ・である調",
        "です・ます",
        "話し言葉",
        "自然な距離感",
        "少し笑える",
        "報告書調",
        "中性的",
        "Evidence / Facts / Sources",
    ):
        assert phrase in voice
    assert "語尾を全部そろえない" in voice
    assert "誇張して盛らない" in voice


def test_scope_separation_reduces_repeated_lecture_and_preserves_review() -> None:
    assert len(CONVERSATIONAL_VOICE_POLICY) <= 700
    assert len(EDITORIAL_EXPERIENCE_POLICY) <= 650
    assert len(P5_FINAL_EDITORIAL_POLISH) <= 750

    case = READY_CASES[1].case
    bundle = build_editorial_bundle_prompt(case)
    stage = build_editorial_stage_prompts(case)
    assert bundle.count("【P5 会話の温度とテンポ】") == 1
    assert bundle.count("【P5 最終調整：読者への引力と事実の境界】") == 1
    assert "Fact-Safe Review" in bundle
    assert FACT_SAFE_FULL_MANUSCRIPT_CONTRACT in bundle
    assert "必ずMarkdown H1" in bundle
    assert "Fact-Safe Review" in stage


def test_planning_fields_are_editor_notes_not_forced_autobiography() -> None:
    case = READY_CASES[1].case
    prompts = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    for text in (prompts["Persona Article Generation"], bundle):
        assert "編集メモは記事に写さない" in text
        assert "before→after" in text
        assert "writer-owned anchor" in text
        assert "Writer Question" in text
        assert "What I Now Find Interesting" in text
        assert "無理に『私』の感想を足さない" in text
        assert "口語でも根拠は変えない" in text


def test_frozen_b_is_not_exposed_to_p5_colloquial_changes() -> None:
    case = READY_CASES[1].case
    b = build_persona_only_prompt(case)
    for policy in (CONVERSATIONAL_VOICE_POLICY, P5_FINAL_EDITORIAL_POLISH, EDITORIAL_EXPERIENCE_POLICY):
        assert policy not in b
    assert "もっと砕けた口語調" not in b
