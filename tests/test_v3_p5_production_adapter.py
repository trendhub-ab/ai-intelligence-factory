"""Provider-free V3 P5 original five-stage editorial integration regression.

No Gemini calls, no Notion/note publication. The REAL five-stage bundled
C-Writer protocol remains separate from canonical MANAGEMENT DATA; Production
Fact/Evidence/Reader/Publication Gates still run after the combined response.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import a_plus_editorial_orchestration as a_plus
from content_generation_protocol import editorial_style_rules
from local_skills.a_plus import PREWRITE_CONTRACT_ID
from local_skills.v3_p5_contract import EDITORIAL_STAGES
from local_skills.v3_p5_one_shot import (
    BASELINE_P5_COMMIT,
    P5EditorialContractError,
    _extract_bundle,
    _p5_prompt,
    _source_case,
)
from local_skills.v3_p5_prompts import build_editorial_bundle_prompt


SPLIT = "===NOTE_DRAFT_START==="
MANAGEMENT = """=== MANAGEMENT DATA ===
・Source Summary: 一次情報の概要。
・What: 何が起きた。
・Why Important: 判断の分かれ目。
・Decision: TRY
・Decision Reason: 根拠が限定される。
・Decision Score: Business Impact 15/25; Technical Impact 14/25; Urgency 9/20; Market Impact 9/15; Reliability 10/15; 合計 57/100
・Action: 限定して検証する。
・Article Value: 72
"""
BASE_RESPONSE = MANAGEMENT + "\n" + SPLIT + "\n初回タイトル。\n初回の記事本文。"
P5_FINAL = "# 新しい発見\n\nまず確かめたいのは、二つの条件が本当に同じなのかということ。\n\n## 数字の意味\n\n数値の差には検証条件がある。\n\n## 次にすること\n\n限定した条件で確かめたい。"


def _bundle(final=P5_FINAL):
    return json.dumps(
        {stage: P5_FINAL if stage == "Persona Article Generation"
         else final if stage == "Fact-Safe Review"
         else f"{stage}: Evidenceと根拠の確認"
         for stage in EDITORIAL_STAGES}, ensure_ascii=False,
    )


def _source():
    return {
        "evidence_result": {"state": "SUFFICIENT", "decision_scope_safe": True},
        "evidence_sufficient": True,
        "verification_context": (
            "Primary source reports an observed numeric comparison under a controlled setup; "
            "the claim is limited to the reported dataset and must not be generalized."
        ),
        "primary_url": "https://example.org/official-report",
        "evidence_metadata": {"required_qualifiers": ["比較は限定条件のみ"]},
    }


def _fake_runtime(style: str, followup: str | None = None):
    sent: list[str] = []

    def parse(raw):
        if SPLIT not in raw:
            return {}
        rest = raw.split(SPLIT, 1)[1].strip()
        lines = rest.split("\n", 1)
        return {
            "title_text": lines[0].strip(), "note_draft": lines[1].strip() if len(lines) > 1 else "",
            "source_summary_text": "一次情報の概要。",
            "decision_text": "TRY",
            "decision_reason_text": "根拠が限定される。",
            "action_text": "限定して検証する。",
        }

    def generate(prompt, repo, source_info, **kw):
        sent.append(prompt)
        return (
            SimpleNamespace(text=BASE_RESPONSE if len(sent) == 1 else followup, candidates=[]),
            {"grounding_status": "Source Native"},
        )

    p = SimpleNamespace(
        AIIF_EDITORIAL_STYLE=style,
        EVIDENCE_SUFFICIENT="SUFFICIENT",
        SECTION_SPLIT_TOKEN=SPLIT,
        build_decision_prompt=lambda *a, **kw: (
            "Evidence rules\n【Output Contract｜完成稿のみ】\n"
        ),
        _parse_gemini_response=parse,
        should_attempt_dynamic_retry=lambda *a, **kw: (False, "none"),
        call_gemini_grounded_deep_dive=generate,
        generate_intelligence_report=lambda *a, **kw: None,
        logger=None,
    )
    a_plus.install(p)
    return p, sent


def test_p5_full_five_stage_source_is_routed_and_all_original_stages_exist():
    assert BASELINE_P5_COMMIT == "95016a65701979063f56130bf181bca831661f5d"
    assert EDITORIAL_STAGES == (
        "Writer Reaction", "Editorial Discovery", "Cognitive Shift",
        "Persona Article Generation", "Fact-Safe Review",
    )
    case = _source_case({"name": "Test", "url": "https://example.org/official-report"}, _source(), SimpleNamespace(EVIDENCE_SUFFICIENT="SUFFICIENT"))
    prompt = build_editorial_bundle_prompt(case)
    assert prompt.index("1. Writer Reaction") < prompt.index("2. Editorial Discovery")
    assert prompt.index("2. Editorial Discovery") < prompt.index("3. Cognitive Shift")
    assert prompt.index("3. Cognitive Shift") < prompt.index("4. Persona Article Generation")
    assert prompt.index("4. Persona Article Generation") < prompt.index("5. Fact-Safe Review")
    assert "【P5 会話の温度とテンポ】" in prompt
    assert "次の5キーだけを持つ有効なJSON object" in prompt
    assert _p5_prompt(case, {
        "source_summary_text": "概要", "decision_text": "TRY", "action_text": "検証する"
    }, _source()).startswith(prompt)
    assert "Local Skills" in _p5_prompt(case, {
        "source_summary_text": "概要", "decision_text": "TRY", "action_text": "検証する"
    }, _source())


def test_p5_editorial_engine_performs_real_two_call_schema_compatible_handoff():
    p, sent = _fake_runtime("v3_p5", followup=_bundle())
    first_prompt = p.build_decision_prompt(evidence_result={"state": "SUFFICIENT"})
    response, _ = p.call_gemini_grounded_deep_dive(
        first_prompt, {"name": "Test", "url": "https://example.org/official-report"},
        _source(), request_kind="deep_dive", request_context="OfficialVendor:Test",
    )
    assert len(sent) == 2, "one management call + one five-stage P5 bundle"
    assert sent[0] == first_prompt
    assert sent[1].count("【Production A+ LocalSkills / Gate Authority｜全5段階で遵守】") == 1
    assert sent[1].count("5. Fact-Safe Review") == 1
    assert first_prompt.count(PREWRITE_CONTRACT_ID) == 1
    assert response.text.split(SPLIT, 1)[0].strip() == MANAGEMENT.strip()
    assert "# 新しい発見" not in response.text
    assert "新しい発見。" in response.text
    assert "限定した条件で確かめたい。" in response.text
    assert "初回の記事本文。" not in response.text
    assert "Writer Reaction:" not in response.text
    assert p._parse_gemini_response(response.text)["decision_text"] == "TRY"


def test_p5_invalid_bundle_fails_closed_without_classic_fallback():
    p, sent = _fake_runtime("v3_p5", followup='{"Fact-Safe Review":"# 見出し\\n本文"}')
    prompt = p.build_decision_prompt(evidence_result={"state": "SUFFICIENT"})
    with pytest.raises(P5EditorialContractError, match="five stages"):
        p.call_gemini_grounded_deep_dive(
            prompt, {"name": "Test"}, _source(), request_kind="deep_dive",
        )
    assert len(sent) == 2


def test_p5_incomplete_source_requires_verified_evidence():
    p, sent = _fake_runtime("v3_p5", followup=_bundle())
    src = _source()
    src["evidence_sufficient"] = False
    src["evidence_result"] = {"state": "INSUFFICIENT"}
    with pytest.raises(P5EditorialContractError, match="sufficient source"):
        p.call_gemini_grounded_deep_dive(
            p.build_decision_prompt(evidence_result=src["evidence_result"]),
            {"name": "Test"}, src, request_kind="deep_dive",
        )
    assert len(sent) == 1


def test_classic_stays_one_call_and_router_is_default_classic():
    assert editorial_style_rules("v3_p5") == editorial_style_rules("classic")
    assert editorial_style_rules("human_narrative") != editorial_style_rules("classic")
    with pytest.raises(ValueError, match="unknown editorial style"):
        editorial_style_rules("v3_p51")
    p, sent = _fake_runtime("classic", followup=_bundle())
    prompt = p.build_decision_prompt(evidence_result={"state": "SUFFICIENT"})
    response, _ = p.call_gemini_grounded_deep_dive(
        prompt, {"name": "Test"}, _source(), request_kind="deep_dive",
    )
    assert len(sent) == 1
    assert response.text == BASE_RESPONSE


def test_original_p5_article_parser_rejects_leaked_internal_verdict():
    good, stages = _extract_bundle(_bundle())
    assert good.startswith("# 新しい発見")
    assert set(stages) == set(EDITORIAL_STAGES)
    with pytest.raises(P5EditorialContractError, match="stage validation"):
        _extract_bundle(_bundle(final=P5_FINAL.replace("限定した", "TRY 限定した")))


def test_one_shot_option_preserves_existing_sources_and_publication_gates():
    workflow = Path(".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    assert "default: 'classic'" in workflow
    assert "          - v3_p5" in workflow
    assert "classic|human_narrative|duo_narrative|v3_p5)" in workflow
    assert "run: python production_pipeline.py" in workflow
    assert "AIIF_EDITORIAL_STYLE: ${{ inputs.editorial_style }}" in workflow
    assert "group: ai-intelligence-gemini-budget" in workflow
    assert "if: ${{ inputs.confirm == 'RUN_ONCE' }}" in workflow
    assert "GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET: \"12\"" in workflow
    source = Path("note_manuscript.py").read_text(encoding="utf-8")
    assert '("どんな内容？",' in source
    assert '("なぜ重要？",' in source
    assert '("結論は？",' in source
    assert 'f"### Sources / Evidence\\n"' in source


def test_p5_first_pass_decision_stays_in_management_but_never_leaks_to_second_prompt():
    case = _source_case(
        {"name": "Test", "url": "https://example.org/official-report"},
        _source(), SimpleNamespace(EVIDENCE_SUFFICIENT="SUFFICIENT"),
    )
    incoming = {
        "source_summary_text": "この手法は動向注視。",
        "decision_text": "WATCH",
        "decision_reason_text": "現時点ではWATCHの理由として独立検証が必要。",
        "action_text": "注視（WATCH）しつつ研究で確認する。",
    }
    prompt = _p5_prompt(case, incoming, _source())
    assert "現時点" in prompt
    assert "研究で確認する。" in prompt
    # The immutable original P5 instructions *intentionally* mention WATCH to forbid
    # reader-facing leakage. Only the injected management guidance may not contain it.
    assert "WATCH" not in prompt.split("【Production A+ LocalSkills / Gate Authority｜全5段階で遵守】", 1)[1]
    assert "Decision (existing canonical management classification)" not in prompt
    assert "【Production A+ LocalSkills / Gate Authority｜全5段階で遵守】" in prompt


def test_p5_precise_observed_watch_leak_is_corrected_and_original_fact_gate_stays_strict():
    observed = P5_FINAL + "\n\n現段階では**注視（WATCH）**しつつ、実験で検証したい。"
    final, stages = _extract_bundle(_bundle(final=observed))
    assert "WATCH" not in final
    assert final.endswith("現段階では**注視**しつつ、実験で検証したい。")
    assert stages["Fact-Safe Review"] == final
    assert stages["Persona Article Generation"] == P5_FINAL

    for invalid in (
        P5_FINAL + "\n何よりもWATCHすべき。",
        P5_FINAL + "\nこの結果はTRYだ。",
        P5_FINAL + "\n注視（WATCH）しつつ、WATCH。",
        P5_FINAL + "\n注視（WATCH）と注視（WATCH）。",
    ):
        with pytest.raises(P5EditorialContractError, match="stage validation"):
            _extract_bundle(_bundle(final=invalid))
