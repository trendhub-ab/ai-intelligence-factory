from pathlib import Path

import content_generation_protocol as cgp
import pipeline


ROOT = Path(__file__).resolve().parents[1]


def _prompt():
    return pipeline.build_decision_prompt(
        "fixture",
        "https://example.com/source",
        0,
        "fixture description",
        source_context="Primary evidence with verified facts and limits.",
    )


def test_duo_narrative_is_a_third_style_without_replacing_existing_choices():
    assert cgp.EDITORIAL_STYLE_CHOICES == (
        "classic",
        "human_narrative",
        "duo_narrative",
    )
    assert cgp.editorial_style_rules("classic") == cgp._human_editorial_style_rules()
    assert "[AIIF_HUMAN_NARRATIVE_EDITORIAL_STYLE_V1]" in cgp.editorial_style_rules("human_narrative")


def test_duo_narrative_builds_on_human_narrative_and_adds_character_contract(monkeypatch):
    monkeypatch.setattr(pipeline, "AIIF_EDITORIAL_STYLE", "duo_narrative", raising=False)
    prompt = _prompt()
    assert "[AIIF_HUMAN_NARRATIVE_EDITORIAL_STYLE_V1]" in prompt
    assert "[AIIF_DUO_NARRATIVE_EDITORIAL_STYLE_V1]" in prompt
    assert "フェルン" in prompt
    assert "クレハ" in prompt
    assert "fetch" in prompt
    assert "clever" in prompt


def test_duo_roles_are_complementary_not_expert_and_dummy():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "技術のキモ" in rules
    assert "少し理屈っぽく" in rules
    assert "専門家ではないが、頭の回転が速い" in rules
    assert "それって要するにどういうこと" in rules
    assert "それ、本当にすごいの" in rules
    assert "誰が得するの" in rules


def test_duo_dialogue_is_a_bridge_not_the_whole_article():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "記事全体を台本形式にしない" in rules
    assert "導入・難所の説明・話題の転換・結び" in rules
    assert "会話比率を固定ノルマにしない" in rules
    assert "本文の理解を進める場合だけ" in rules


def test_duo_dialogue_cannot_invent_facts_or_personal_experience():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "キャラクターは事実源ではない" in rules
    assert "根拠のない数値・性能・価格・市場評価" in rules
    assert "架空の利用経験" in rules
    assert "会話だから許される" in rules
    assert "Fact Disciplineを読者に見せる" in rules


def test_duo_ending_uses_varied_everyday_landing_not_a_fixed_sock_joke():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "靴下" in rules
    assert "毎回同じ日常ネタ" in rules
    assert "記事テーマとつながる身近な現実" in rules
    assert "固定オチ" in rules


def test_one_shot_workflow_exposes_duo_narrative_choice():
    text = (ROOT / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    assert "- duo_narrative" in text
    assert "classic|human_narrative|duo_narrative" in text
