from __future__ import annotations

import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")

import canonical_article_contract as contract
import pipeline


def test_hypothetical_industry_standard_is_not_a_current_standard_claim():
    failures = pipeline._find_hype_claims(
        "この枠組みが将来、業界標準となれば、比較基準をそろえやすくなります。",
        source_context="There is no industry-wide framework today. We hope this is a first step toward creating such standards.",
        evidence_metadata={},
    )
    assert not any("market-standard" in item for item in failures)


def test_present_industry_standard_assertion_remains_blocked():
    failures = pipeline._find_hype_claims(
        "この枠組みは業界標準です。",
        source_context="There is no industry-wide framework today.",
        evidence_metadata={},
    )
    assert "unsupported market-standard claim: 業界標準" in failures


def test_heading_like_current_standard_assertion_remains_blocked():
    failures = pipeline._find_hype_claims(
        "業界標準としての報告基準に注目する",
        source_context="We hope this is a first step toward creating such standards.",
        evidence_metadata={},
    )
    assert "unsupported market-standard claim: 業界標準" in failures


def test_hard_retry_names_vague_quantity_and_market_standard_actions_explicitly():
    rows = [
        {
            "reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM,
            "severity": pipeline.GATE_SEVERITY_HARD,
            "message": "unsupported vague quantified claim: 数ヶ月",
        },
        {
            "reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM,
            "severity": pipeline.GATE_SEVERITY_HARD,
            "message": "unsupported market-standard claim: 業界標準",
        },
    ]
    instruction, sections = pipeline.build_dynamic_retry_instruction(rows)
    assert "『数ヶ月』" in instruction
    assert "別の期間や数量を推測して置き換えてはいけません" in instruction
    assert "『業界標準』" in instruction
    assert "現在すでに業界標準であるように読める見出し・本文" in instruction
    assert "標準化の事実を新しく作ってはいけません" in instruction
    assert "claims" in sections


def test_writer_contract_preserves_quantity_and_standardization_scope():
    text = contract.canonical_writer_contract()
    assert "曖昧な数量" in text
    assert "「しばらく」「数ヶ月」「数倍」" in text
    assert "将来の業界標準になればよい" in text
    assert "現在の確立済み事実へ強めない" in text
    assert "見出しでも同じSource Boundary" in text
