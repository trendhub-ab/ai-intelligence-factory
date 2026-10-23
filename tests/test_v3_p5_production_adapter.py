"""Provider-free contract tests for the optional V3 P5 production writer adapter.

Freeze the editorial policy; preserve canonical LocalSkills, schema, and gates.
This is NOT an experimental five-stage provider-call proof or a publication GO.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import a_plus_editorial_orchestration as a_plus
from content_generation_protocol import editorial_style_rules
from local_skills.a_plus import PREWRITE_CONTRACT_ID
from local_skills.v3_p5_writer import (
    FROZEN_P5_COMMIT,
    P5_FROZEN_POLICY_NAMES,
    build_v3_p5_writer_contract,
)


def test_selected_p5_policy_is_frozen_and_provider_free():
    assert FROZEN_P5_COMMIT == "95016a65701979063f56130bf181bca831661f5d"
    text = build_v3_p5_writer_contract()
    assert text == build_v3_p5_writer_contract()
    assert len(P5_FROZEN_POLICY_NAMES) == 6
    assert text.count("【P5 最終調整：読者への引力と事実の境界】") == 1
    assert text.count("【P5 対照例：会話調は具体性でつくる】") == 1
    assert "女子高生というWriterの背景設定" in text
    assert "架空の実体験" in text or "架空の体験" in text
    assert "根拠" in text and "Evidence" in text
    assert not any(token in text for token in ("gemini.generate_content(", "API_KEY", "openai.com/"))
    src = Path("local_skills/v3_p5_writer.py").read_text(encoding="utf-8")
    assert "experiments.editorial_engine_v3_phase0" not in src


def test_style_router_selects_v3_p5_without_mutating_classic():
    normal = editorial_style_rules("classic")
    selected = editorial_style_rules("v3_p5")
    assert "【Human Editorial Style｜最重要】" in normal
    assert "【Human Editorial Style｜最重要】" in editorial_style_rules()
    assert normal != selected
    assert selected == build_v3_p5_writer_contract()
    for other in ("human_narrative", "duo_narrative"):
        assert editorial_style_rules(other) != selected
    with pytest.raises(ValueError, match="unknown editorial style"):
        editorial_style_rules("v3_p51")


def test_local_skills_contract_is_injected_before_output_schema_with_p5():
    marker = "\n【Output Contract｜完成稿のみ】"
    p = SimpleNamespace(
        build_decision_prompt=lambda **kw: "Evidence rule\n" + editorial_style_rules(kw["style"]) + marker + "\n=== MANAGEMENT DATA ===",
        _parse_gemini_response=lambda *a, **kw: {"title_text": "記事タイトル", "note_draft": "本文"},
        should_attempt_dynamic_retry=lambda *a, **kw: (False, "none"),
        call_gemini_grounded_deep_dive=lambda *a, **kw: None,
        generate_intelligence_report=lambda *a, **kw: None,
        logger=None,
    )
    a_plus.install(p)
    selected = p.build_decision_prompt(style="v3_p5", evidence_result={"state": "SUFFICIENT"})
    assert selected.index("【P5 会話の温度とテンポ】") < selected.index(PREWRITE_CONTRACT_ID)
    assert selected.index(PREWRITE_CONTRACT_ID) < selected.index(marker)
    assert selected.count(PREWRITE_CONTRACT_ID) == 1
    assert "=== MANAGEMENT DATA ===" in selected
    classic = p.build_decision_prompt(style="classic", evidence_result={"state": "SUFFICIENT"})
    assert "【P5 会話の温度とテンポ】" not in classic
    assert classic.count(PREWRITE_CONTRACT_ID) == 1
    assert p._parse_gemini_response()["note_draft"] == "本文"


def test_manual_daily_opt_in_no_default_flip_and_no_extra_provider_calls():
    workflow = Path(".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    assert "default: 'classic'" in workflow
    assert "          - v3_p5" in workflow
    assert "classic|human_narrative|duo_narrative|v3_p5)" in workflow
    assert "run: python production_pipeline.py" in workflow
    assert "AIIF_EDITORIAL_STYLE: ${{ inputs.editorial_style }}" in workflow
    assert "AIIF_RUN_MODE: ${{ inputs.mode }}" in workflow
    assert "group: ai-intelligence-gemini-budget" in workflow
    assert "if: ${{ inputs.confirm == 'RUN_ONCE' }}" in workflow
    assert "AIIF_LOCAL_SKILLS_PRODUCTION_VALIDATION: ${{ inputs.mode == 'local_skills_production_validation' }}" in workflow
