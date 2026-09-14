"""Zero-network characterization tests for the diagnostic publish-yield replay."""

from copy import deepcopy

from publish_yield_replay import (
    CATEGORY_CURRENT_READY,
    CATEGORY_HUMAN_APPEAL_ONLY,
    CATEGORY_OTHER_REVIEW,
    CATEGORY_SAFETY_BLOCKED,
    classify_candidate,
    evaluate_publish_yield,
)


def appeal(message="reader_value_review:dense_report_cluster"):
    return {"gate": "human_appeal", "message": message}


def fact(message="unsupported numeric claim: 44 minutes"):
    return {"gate": "fact", "message": message}


def evidence(message="primary_evidence_insufficient"):
    return {"gate": "evidence", "message": message}


def publication(message="headline_overclaim"):
    return {"gate": "publication", "message": message}


def test_hard_safety_reasons_can_never_be_counted_as_human_appeal_only():
    for hard_reason in (fact(), evidence(), publication()):
        record = {"final_status": "Needs Editorial Review", "reason_rows": [hard_reason]}
        assert classify_candidate(record) == CATEGORY_SAFETY_BLOCKED


def test_mixed_human_appeal_and_fact_stays_safety_blocked():
    record = {
        "final_status": "Needs Editorial Review",
        "reason_rows": [appeal(), fact()],
    }
    assert classify_candidate(record) == CATEGORY_SAFETY_BLOCKED


def test_human_appeal_only_is_diagnostic_and_does_not_mutate_input():
    record = {
        "id": "reader-only",
        "final_status": "Needs Editorial Review",
        "reason_rows": [appeal("reader_value_review:non_engineer_access_failure")],
    }
    before = deepcopy(record)
    assert classify_candidate(record) == CATEGORY_HUMAN_APPEAL_ONLY
    assert record == before
    assert record["final_status"] == "Needs Editorial Review"


def test_unknown_or_missing_review_is_not_assumed_recoverable():
    editorial_unknown = {
        "final_status": "Needs Editorial Review",
        "reason_rows": [{"gate": "editorial", "message": "new_unmapped_editorial_issue"}],
    }
    missing_reasons = {"final_status": "Needs Editorial Review", "reason_rows": []}
    assert classify_candidate(editorial_unknown) == CATEGORY_OTHER_REVIEW
    assert classify_candidate(missing_reasons) == CATEGORY_OTHER_REVIEW


def test_current_ready_remains_ready_when_no_contradictory_review_exists():
    assert classify_candidate({"final_status": "Ready", "reason_rows": []}) == CATEGORY_CURRENT_READY


def test_inconsistent_ready_with_hard_reason_fails_closed():
    record = {"final_status": "Ready", "reason_rows": [fact()]}
    assert classify_candidate(record) == CATEGORY_SAFETY_BLOCKED


def test_nonready_soft_only_reason_does_not_inflate_recoverable_ceiling():
    record = {
        "final_status": "Needs Editorial Review",
        "reason_rows": [
            {
                "gate": "human_appeal",
                "message": "headline_flattened",
                "severity": "SOFT_QUALITY",
            }
        ],
    }
    assert classify_candidate(record) == CATEGORY_OTHER_REVIEW


def test_run51_shape_reflects_post_split_reason_dispositions():
    # This generic five-row fixture is intentionally diagnostic only. Under the core-vs-style
    # split, dense/style-only Reader reasons are SOFT and therefore are not counted as a
    # recoverable REVIEW ceiling. The one remaining human-appeal REVIEW here is Decision Voice.
    records = [
        {"id": "hard-fact", "final_status": "Hard Block", "reason_rows": [fact()]},
        {"id": "hard-evidence", "final_status": "Hard Block", "reason_rows": [evidence()]},
        {"id": "appeal-1", "final_status": "Needs Editorial Review", "reason_rows": [appeal()]},
        {
            "id": "appeal-2",
            "final_status": "Needs Editorial Review",
            "reason_rows": [appeal("decision_voice_missing")],
        },
        {
            "id": "appeal-3",
            "final_status": "Needs Editorial Review",
            "reason_rows": [appeal("reader_value_review:multi_axis_reader_weakness")],
        },
    ]

    report = evaluate_publish_yield(records)
    assert report["diagnostic_only"] is True
    assert report["total_count"] == 5
    assert report["current_ready_count"] == 0
    assert report["current_ready_yield"] == 0.0
    assert report["safety_blocked_count"] == 2
    assert report["human_appeal_only_count"] == 1
    assert report["other_review_count"] == 2
    assert report["recoverable_ceiling_count"] == 1
    assert report["recoverable_ceiling_yield"] == 0.2


def test_empty_input_is_well_defined():
    report = evaluate_publish_yield([])
    assert report["total_count"] == 0
    assert report["current_ready_yield"] == 0.0
    assert report["recoverable_ceiling_yield"] == 0.0
