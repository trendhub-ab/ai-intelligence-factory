from pathlib import Path

import pytest

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


def test_classic_style_remains_the_existing_default_contract(monkeypatch):
    assert cgp.editorial_style_rules("classic") == cgp._human_editorial_style_rules()
    monkeypatch.setattr(pipeline, "AIIF_EDITORIAL_STYLE", "classic", raising=False)
    prompt = _prompt()
    assert "【Human Editorial Style｜最重要】" in prompt
    assert "[AIIF_HUMAN_NARRATIVE_EDITORIAL_STYLE_V1]" not in prompt


def test_human_narrative_style_is_selectable_without_changing_evidence_contract(monkeypatch):
    monkeypatch.setattr(pipeline, "AIIF_EDITORIAL_STYLE", "human_narrative", raising=False)
    prompt = _prompt()
    assert "[AIIF_HUMAN_NARRATIVE_EDITORIAL_STYLE_V1]" in prompt
    assert "SOURCE BOUNDARY — 最重要" in prompt
    assert "Evidence-to-Decisionの安全制約" in prompt
    assert "架空の実体験" in prompt
    assert "専門内容へ必ず戻る" in prompt


def test_human_narrative_style_encodes_varied_humor_not_a_new_template():
    rules = cgp.editorial_style_rules("human_narrative")
    assert "人間が頭の中で場面を描ける入口" in rules
    assert "1セクションに必ず1回" in rules
    assert "ノルマにしない" in rules
    assert "同じ比喩・会社員ネタ・擬人化を別記事へ使い回さない" in rules
    assert "事実・数値・制約・反証・Decisionを笑いのために弱めない" in rules
    assert "実体験のように見える一人称" in rules


def test_unknown_editorial_style_fails_closed():
    with pytest.raises(ValueError, match="unknown editorial style"):
        cgp.editorial_style_rules("surprise_me")


def test_one_shot_workflow_allows_explicit_style_selection():
    text = (ROOT / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    assert "editorial_style:" in text
    assert "default: 'classic'" in text
    assert "- classic" in text
    assert "- human_narrative" in text
    assert "AIIF_EDITORIAL_STYLE: ${{ inputs.editorial_style }}" in text
