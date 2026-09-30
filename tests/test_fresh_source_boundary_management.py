"""Offline regression for the real 2026-09-30 HackerNews Fresh BLOCK.

Historical archived artifact from Run 36688118222:
- source OpenAI DevDay Recap 2026, Polish primary URL
- action copied provider management text containing "ChatGPT Plus"
- Fact source boundary BLOCK despite Editorial/Human/Publication passing.

These fixtures test *the recorded source-verification surface*, NOT a new
Fresh PASS and NOT a claim that the actual official page lacks Plus. The
public English primary announcement explicitly includes Plus availability,
but that text was not proved present in the historical verification context.
"""
from __future__ import annotations

import copy

import pytest
import pipeline
from local_skills.production_canary import (
    _scope_unsupported_management_claims, apply_to_production_parsed,
)


PRIMARY = "https://openai.com/pl-PL/index/devday-2026-recap/"
REPO = {"nameWithOwner": "OpenAI DevDay Recap – what's new",
        "source": "HackerNews", "url": PRIMARY, "primaryUrl": PRIMARY}

# Multilingual source excerpt: direct source names the model and Plus plan,
# but does not explicitly spell the *compound* named entity ChatGPT Plus.
# Crucially do not convert these separated words into new evidence.
RECORDED_CONTEXT_SHAPE = (
    "DevDay 2026: ChatGPT, Codex, more than 20 major announcements. "
    "GPT-6.1 Sol. Dostępny dla wszystkich użytkowników API oraz planów Plus, "
    "Pro, Business, Enterprise i Edu. "
)
ACTION = (
    "APIおよびChatGPT PlusやProなどの上位プランで提供が開始された"
    "GPT-6.1 Solを試験的に導入し、費用対効果を評価します。"
)


def _parsed():
    return {
        "title_text": "PROVIDER TITLE SHOULD NOT SURVIVE",
        "note_draft": "PROVIDER BODY SHOULD NOT SURVIVE",
        "score": 81,
        "decision_text": "TRY",
        "decision_reason_text": "公式発表の新機能を、自社環境の小規模検証で評価します。",
        "source_summary_text": "OpenAIがDevDay 2026で新機能を発表しました。",
        "what_text": "GPT-6.1 Solが発表され、API向けの機能が増えました。",
        "why_important_text": "自社向けの開発手段を比較する判断材料になります。",
        "action_text": ACTION,
        "main_risk_text": "",
        "best_for_text": "",
        "avoid_for_text": "",
    }


def _compile(parsed, context):
    return apply_to_production_parsed(
        REPO, parsed, source="HackerNews", primary_url=PRIMARY,
        grounding={"evidence_urls": [PRIMARY]},
        evidence_context=context,
        source_boundary_checker=pipeline._find_source_boundary_violations,
    )


def test_historical_unsupported_compound_name_is_actually_detected_before_fix():
    issues = pipeline._find_source_boundary_violations(
        ACTION, RECORDED_CONTEXT_SHAPE, REPO["nameWithOwner"]
    )
    assert any("ChatGPT Plus" in issue for issue in issues), issues


def test_precompile_scope_replaces_only_unproven_provider_action_and_syncs_article():
    original = _parsed()
    unmutated = copy.deepcopy(original)
    output, meta = _compile(original, RECORDED_CONTEXT_SHAPE)
    precision = meta["management_source_boundary_precision"]
    assert precision["status"] == "SCOPED"
    assert precision["replaced_fields"] == ["action_text"]
    assert any("ChatGPT Plus" in issue for issue in precision["issues"])
    assert "ChatGPT Plus" not in output["action_text"]
    assert "ChatGPT Plus" not in output["note_draft"]
    assert "小規模" in output["action_text"]
    assert output["action_text"] in output["note_draft"]
    assert original == unmutated
    assert output["score"] == original["score"]
    assert output["decision_text"] == original["decision_text"]
    assert meta["provider_article_surface_reused"] is False
    assert pipeline._find_source_boundary_violations(
        output["action_text"], RECORDED_CONTEXT_SHAPE, REPO["nameWithOwner"]
    ) == []


def test_source_explicitly_proving_compound_name_preserves_original_action():
    parsed = _parsed()
    direct_evidence = RECORDED_CONTEXT_SHAPE + (
        " GPT-6.1 Sol is available to ChatGPT Plus and Pro subscribers."
    )
    output, meta = _compile(parsed, direct_evidence)
    assert meta["management_source_boundary_precision"]["status"] == "UNCHANGED"
    assert "action_text" not in meta["management_source_boundary_precision"]["replaced_fields"]
    assert "ChatGPT Plus" in output["action_text"]
    assert "GPT-6.1 Sol" in output["action_text"]


def test_unsupported_management_reason_is_separately_scoped():
    parsed = _parsed()
    parsed["decision_reason_text"] = (
        "Enterprise Syncが公式に提供されたため、導入を検討します。"
    )
    output, meta = _compile(parsed, RECORDED_CONTEXT_SHAPE)
    precision = meta["management_source_boundary_precision"]
    assert set(precision["replaced_fields"]) == {"decision_reason_text", "action_text"}
    assert "Enterprise Sync" not in output["decision_reason_text"]
    assert "Enterprise Sync" not in output["note_draft"]


def test_no_verification_evidence_fails_closed_before_compilation():
    with pytest.raises(RuntimeError, match="verified evidence"):
        _compile(_parsed(), "")


def test_unexpected_source_gate_diagnostic_is_never_silenced():
    def other_gate(value, evidence, name):
        return ["unclassified critical error"] if "ChatGPT Plus" in value else []

    with pytest.raises(RuntimeError, match="Unexpected"):
        _scope_unsupported_management_claims(
            _parsed(), evidence_context=RECORDED_CONTEXT_SHAPE,
            repo_name=REPO["nameWithOwner"], source_boundary_checker=other_gate
        )


def test_fallback_must_pass_original_checker_itself():
    def rejects_all(value, evidence, name):
        return ["source-boundary unsupported named fact: generic"] if value else []

    with pytest.raises(RuntimeError, match="fallback failed"):
        _scope_unsupported_management_claims(
            _parsed(), evidence_context=RECORDED_CONTEXT_SHAPE,
            repo_name=REPO["nameWithOwner"], source_boundary_checker=rejects_all
        )


def test_both_historical_experiment_and_production_use_same_gate_checker():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "pipeline.py").read_text(encoding="utf-8")
    assert "source_boundary_checker=_find_source_boundary_violations" in source
    assert 'source_info.get("verification_context")' in source


def test_measured_devday_failure_is_quarantined_across_source_locales():
    from local_skills_daily_canary import _already_observed
    for u in (
        PRIMARY,
        "https://openai.com/index/devday-2026-recap/",
        "https://openai.com/ja-JP/index/devday-2026-recap/",
    ):
        assert _already_observed({"nameWithOwner": "different display title", "url": u})
    assert _already_observed({"nameWithOwner": REPO["nameWithOwner"], "url": "https://example.invalid/other"})
    assert not _already_observed({
        "nameWithOwner": "another untouched topic",
        "url": "https://example.invalid/untouched",
    })
