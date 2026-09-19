import json
from pathlib import Path

import gate_reasoning as gr
import run208_reader_value_repair as r208


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "canonical_article_contract"
    / "run74_reason_cases.json"
)


def _mapped(row):
    return gr.map_gate_reasons(row["gate"], [row["message"]])[0]


def test_observed_daily_reason_classes_keep_one_explicit_owner():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in cases:
        mapped = [_mapped(row) for row in case["rows"]]
        for source, result in zip(case["rows"], mapped):
            assert result["gate"] == source["gate"]
        assert r208.is_reader_only_repair(mapped, gr.GATE_SEVERITY_HARD) is case["reader_only"]


def test_reader_reason_keeps_reader_code_without_becoming_publication_reason():
    row = _mapped(
        {
            "gate": "human_appeal",
            "message": "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)",
        }
    )
    assert row["reason_code"] == gr.REASON_CODE_READER_NON_ENGINEER_ACCESS
    assert row["gate"] == "human_appeal"
    assert row["severity"] == gr.GATE_SEVERITY_REVIEW


def test_fact_conditionality_loss_remains_hard_block():
    row = _mapped(
        {
            "gate": "fact",
            "message": "conditional scope lost from primary evidence",
        }
    )
    assert row["reason_code"] == gr.REASON_CODE_FACT_CONDITIONALITY_LOSS
    assert row["gate"] == "fact"
    assert row["severity"] == gr.GATE_SEVERITY_HARD


def test_unknown_publication_reason_remains_fail_closed():
    row = _mapped(
        {"gate": "publication", "message": "new_unknown_publication_defect"}
    )
    assert row["gate"] == "publication"
    assert row["severity"] == gr.GATE_SEVERITY_HARD
    assert gr.gate_reason_disposition([row]) == gr.GATE_DISPOSITION_BLOCK


def test_zcode_mixed_publication_and_reader_reasons_cannot_be_reader_only_retry():
    case = next(
        case
        for case in json.loads(FIXTURE.read_text(encoding="utf-8"))
        if case["name"] == "ZCode"
    )
    rows = [_mapped(row) for row in case["rows"]]
    assert any(row["gate"] == "publication" for row in rows)
    assert any(row["reason_code"] == gr.REASON_CODE_READER_NON_ENGINEER_ACCESS for row in rows)
    assert r208.is_reader_only_repair(rows, gr.GATE_SEVERITY_HARD) is False
