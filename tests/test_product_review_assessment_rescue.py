from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import product_review_assessment_rescue as rescue


def _pipeline(original):
    return SimpleNamespace(
        persist_decision_intelligence_assessment=original,
        logger=MagicMock(),
    )


def test_market_standard_only_failure_is_weakened_and_revalidated_once():
    calls = []

    def original(repo, parsed, source_info, evidence_result, reviewed_at, *args, **kwargs):
        calls.append(dict(parsed))
        text = " ".join(str(parsed.get(key) or "") for key in rescue._RESCUE_FIELDS)
        if "デファクト" in text or "業界標準" in text:
            return {
                "saved": False,
                "reason": "assessment_invalid",
                "failures": ["unsupported market-standard claim: デファクト"],
            }
        return {"saved": True, "page_id": None}

    pipeline = _pipeline(original)
    rescue.install(pipeline)
    result = pipeline.persist_decision_intelligence_assessment(
        {"nameWithOwner": "org/tool"},
        {
            "short_rationale_text": "デファクトとして利用される。",
            "main_risk_text": "互換性を確認する。",
        },
        {"verification_context": "verified"},
        {"decision_scope_safe": True},
        "2026-10-02T00:00:00+00:00",
    )

    assert result["saved"] is True
    assert len(calls) == 2
    assert calls[0]["short_rationale_text"] == "デファクトとして利用される。"
    assert calls[1]["short_rationale_text"] == "選択肢として利用される。"
    assert "デファクト" not in calls[1]["short_rationale_text"]
    assert "業界標準" not in calls[1]["short_rationale_text"]


def test_mixed_failures_remain_fail_closed_without_second_persistence_call():
    calls = []

    def original(repo, parsed, source_info, evidence_result, reviewed_at, *args, **kwargs):
        calls.append(dict(parsed))
        return {
            "saved": False,
            "reason": "assessment_invalid",
            "failures": [
                "unsupported market-standard claim: デファクト",
                "source-boundary unsupported named fact: Imaginary API",
            ],
        }

    pipeline = _pipeline(original)
    rescue.install(pipeline)
    result = pipeline.persist_decision_intelligence_assessment(
        {"nameWithOwner": "org/tool"},
        {"short_rationale_text": "デファクトでImaginary APIを使う。"},
        {},
        {},
        "2026-10-02T00:00:00+00:00",
    )

    assert result["saved"] is False
    assert len(calls) == 1


def test_non_assessment_failure_is_never_rescued():
    calls = []

    def original(repo, parsed, source_info, evidence_result, reviewed_at, *args, **kwargs):
        calls.append(dict(parsed))
        return {"saved": False, "reason": "persistence_failed", "error": "x"}

    pipeline = _pipeline(original)
    rescue.install(pipeline)
    result = pipeline.persist_decision_intelligence_assessment(
        {"nameWithOwner": "org/tool"},
        {"short_rationale_text": "デファクトとして利用される。"},
        {},
        {},
        "2026-10-02T00:00:00+00:00",
    )

    assert result["reason"] == "persistence_failed"
    assert len(calls) == 1


def test_installer_is_idempotent():
    original = MagicMock(return_value={"saved": True})
    pipeline = _pipeline(original)
    rescue.install(pipeline)
    wrapped = pipeline.persist_decision_intelligence_assessment
    rescue.install(pipeline)
    assert pipeline.persist_decision_intelligence_assessment is wrapped


def test_run203_installs_rescue_only_for_explicit_product_review_runtime():
    source = (Path(__file__).resolve().parents[1] / "run203_runtime_state_channel.py").read_text(encoding="utf-8")
    assert 'AIIF_PRODUCT_REVIEW_RUNTIME' in source
    assert 'product_review_assessment_rescue.install(pipeline_module)' in source
    assert '!= "true"' in source
