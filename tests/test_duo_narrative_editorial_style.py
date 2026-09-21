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


def test_duo_first_pass_targets_actual_reader_value_failures_without_extra_retry():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "Reader Value First-Pass Contract" in rules
    assert "初出で" in rules and "普通の日本語" in rules
    assert "一つの説明段落" in rules and "理解順序" in rules
    assert "実装在庫だけを圧縮" in rules
    assert "それで使う側には何が変わる？" in rules
    assert "同じ内容を本文と会話で二重説明" in rules
    assert "Accessibility / Information Budget / Jargon Translation" in rules
    assert "Non-Engineer Core Clarity / Narrative Pull / Reader Temperature-Rhythm" in rules
    assert "Reader Valueだけの追加Provider Retryは要求しない" in rules


def test_duo_reader_value_contract_keeps_accuracy_and_avoids_fixed_quotas():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "Evidence・重要な数値・能力境界・反証・Decisionは残し" in rules
    assert "新しいFactを足さず" in rules
    assert "固定文字数・固定個数ルールではなく" in rules


def test_duo_reader_blueprint_precedes_prose_and_targets_real_production_failure():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "Reader Blueprint" in rules
    assert rules.index("Reader Blueprint") < rules.index("Reader Value First-Pass Contract")
    for phrase in ("Central Conclusion", "Capability / Limit", "Necessary Jargon Map", "Discard List", "Reader Decision Bridge", "Duo Moments", "Claim Check", "Question Check"):
        assert phrase in rules
    assert "根拠が曖昧なら数値を削る" in rules
    assert "連続する問い" in rules
    assert "追加Provider callではない" in rules


def test_duo_reader_spine_contract_prevents_report_inventory_and_duplicate_exposition():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "Single Reader Spine" in rules
    assert "普通語を先、正式名称を後" in rules
    assert "会話で置換" in rules
    assert "Decisionを変えない実装名" in rules
    assert "本文へ持ち込まない" in rules
    assert "一つの主張、一つの意味、一つの制約" in rules


def test_duo_final_surface_check_blocks_claim_amplification_before_output():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "Final Claim + Reader Surface Check" in rules
    assert "因果へ格上げ" in rules
    assert "Source Native Context" in rules
    assert "削除・弱化" in rules
    assert "新しいFactを追加しない" in rules
    assert "追加Provider callを使わない" in rules


def test_duo_canonical_pattern_compresses_implementation_inventory_and_unifies_action():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "Canonical Reader Pattern" in rules
    assert "1〜2個" in rules
    assert "Decision / Action Spine" in rules
    assert "最終Decisionと矛盾" in rules


def test_duo_canonical_pattern_removes_unsupported_certainty_and_makes_dialogue_advance_reasoning():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "断定強度" in rules
    assert "間違いない" in rules
    assert "確実" in rules
    assert "違和感 → 検証 → 判断" in rules
    assert "説明の挿入" in rules
    assert "追加Provider callを使わない" in rules


def test_duo_intro_claim_ceiling_is_source_native_and_same_call():
    rules = cgp.editorial_style_rules("duo_narrative")
    assert "Intro Claim Ceiling" in rules
    assert "導入・タイトル・冒頭フック" in rules
    assert "Source Native Context" in rules
    assert "Evidenceより強い未来予測" in rules
    assert "Evidenceより強い因果" in rules
    assert "削除または弱化" in rules
    assert "同一生成call" in rules
    assert "追加Provider callを使わない" in rules
