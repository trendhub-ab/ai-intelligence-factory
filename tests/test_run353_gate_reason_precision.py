from __future__ import annotations

import gate_reasoning as gr


def test_publication_score_narrative_mismatch_is_review_not_hard_block():
    rows = gr.map_gate_reasons("publication", ["score_narrative_mismatch"])
    assert rows == [{
        "reason_code": gr.REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH,
        "message": "score_narrative_mismatch",
        "gate": "publication",
        "severity": gr.GATE_SEVERITY_REVIEW,
    }]
    assert gr.gate_reason_disposition(rows) == gr.GATE_DISPOSITION_REVIEW


def test_publication_article_structure_needs_edit_is_review_not_hard_block():
    rows = gr.map_gate_reasons("publication", ["article_structure_needs_edit"])
    assert rows[0]["reason_code"] == gr.REASON_CODE_STRUCTURE_MISSING
    assert rows[0]["severity"] == gr.GATE_SEVERITY_REVIEW
    assert gr.gate_reason_disposition(rows) == gr.GATE_DISPOSITION_REVIEW


def test_publication_overclaim_and_evidence_failures_remain_hard_block():
    for message in (
        "headline_overclaim",
        "intro_overclaim",
        "research_to_production_leap",
        "marketing_claim_adoption",
        "negative_evidence_omission",
        "primary_evidence_insufficient",
        "unknown_publication_safety_failure",
    ):
        rows = gr.map_gate_reasons("publication", [message])
        assert rows[0]["severity"] == gr.GATE_SEVERITY_HARD, message
        assert gr.gate_reason_disposition(rows) == gr.GATE_DISPOSITION_BLOCK, message


def test_fact_and_evidence_remain_fail_closed():
    fact = gr.map_gate_reasons("fact", ["unsupported numeric claim: 999%"])
    evidence = gr.map_gate_reasons("evidence", ["primary_evidence_insufficient"])
    assert fact[0]["severity"] == gr.GATE_SEVERITY_HARD
    assert evidence[0]["severity"] == gr.GATE_SEVERITY_HARD
    assert gr.gate_reason_disposition(fact) == gr.GATE_DISPOSITION_BLOCK
    assert gr.gate_reason_disposition(evidence) == gr.GATE_DISPOSITION_BLOCK


def test_reader_dense_report_gets_reader_code_not_decision_voice():
    message = (
        "reader_value_review:dense_report_cluster "
        "(Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)"
    )
    rows = gr.map_gate_reasons("human_appeal", [message])
    assert rows[0]["reason_code"] == gr.REASON_CODE_READER_DENSE_REPORT
    assert rows[0]["reason_code"] != gr.REASON_CODE_APPEAL_DECISION_VOICE_LOSS
    assert rows[0]["severity"] == gr.GATE_SEVERITY_REVIEW


def test_reader_specific_codes_cover_current_production_labels():
    cases = {
        "reader_value_review:repetitive_insight": gr.REASON_CODE_READER_REPETITIVE_INSIGHT,
        "reader_value_review:multi_axis_reader_weakness (accessibility/jargon_translation)": gr.REASON_CODE_READER_MULTI_AXIS_WEAKNESS,
        "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)": gr.REASON_CODE_READER_NON_ENGINEER_ACCESS,
        "reader_value_review:final_surface_summary_jargon_cluster (何が出た？/なぜ重要？)": gr.REASON_CODE_READER_FINAL_SURFACE,
        "reader_value_review:future_reader_signal": gr.REASON_CODE_READER_VALUE_OTHER,
    }
    for message, expected in cases.items():
        assert gr.reason_code(message, "human_appeal") == expected, message
        rows = gr.map_gate_reasons("human_appeal", [message])
        assert rows[0]["severity"] == gr.GATE_SEVERITY_REVIEW, message


def test_reader_code_round_trip_infers_human_appeal_gate():
    row = {
        "reason_code": gr.REASON_CODE_READER_DENSE_REPORT,
        "message": "reader_value_review:dense_report_cluster",
    }
    normalized = gr.normalize_gate_reason_rows([row])
    assert normalized[0]["gate"] == "human_appeal"
    assert normalized[0]["severity"] == gr.GATE_SEVERITY_REVIEW


def test_real_decision_voice_still_maps_to_appeal_decision_voice_loss():
    rows = gr.map_gate_reasons("human_appeal", ["decision_voice_missing"])
    assert rows[0]["reason_code"] == gr.REASON_CODE_APPEAL_DECISION_VOICE_LOSS
    assert rows[0]["severity"] == gr.GATE_SEVERITY_REVIEW


def test_mixed_publication_review_and_hard_stays_blocked():
    rows = gr.map_gate_reasons(
        "publication",
        ["score_narrative_mismatch", "headline_overclaim"],
    )
    assert {row["severity"] for row in rows} == {
        gr.GATE_SEVERITY_REVIEW,
        gr.GATE_SEVERITY_HARD,
    }
    assert gr.gate_reason_disposition(rows) == gr.GATE_DISPOSITION_BLOCK
