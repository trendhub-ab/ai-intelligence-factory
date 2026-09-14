"""Zero-API safety tests for Reader core-comprehension vs style-only severity."""

from gate_reasoning import (
    GATE_DISPOSITION_BLOCK,
    GATE_DISPOSITION_PASS_WITH_WARNINGS,
    GATE_DISPOSITION_REVIEW,
    GATE_SEVERITY_HARD,
    GATE_SEVERITY_REVIEW,
    GATE_SEVERITY_SOFT,
    gate_reason_disposition,
    map_gate_reasons,
)


def _reader(*messages: str) -> list[dict]:
    return map_gate_reasons("human_appeal", list(messages))


def test_style_only_reader_density_is_publishable_with_warning():
    rows = _reader(
        "reader_value_review:dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)",
        "reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/narrative_pull/information_budget/reader_temperature_rhythm)",
    )
    assert {row["severity"] for row in rows} == {GATE_SEVERITY_SOFT}
    assert gate_reason_disposition(rows) == GATE_DISPOSITION_PASS_WITH_WARNINGS


def test_non_engineer_core_access_remains_publication_stopping():
    rows = _reader(
        "reader_value_review:multi_axis_reader_weakness (accessibility/curiosity_pull/reader_enjoyment/jargon_translation/non_engineer_core_clarity)",
        "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)",
    )
    assert rows[0]["severity"] == GATE_SEVERITY_REVIEW
    assert rows[1]["severity"] == GATE_SEVERITY_REVIEW
    assert gate_reason_disposition(rows) == GATE_DISPOSITION_REVIEW


def test_multi_axis_with_core_marker_fails_closed_without_companion_reason():
    rows = _reader(
        "reader_value_review:multi_axis_reader_weakness (reader_enjoyment/jargon_translation/information_budget/non_engineer_core_clarity)"
    )
    assert rows[0]["severity"] == GATE_SEVERITY_REVIEW
    assert gate_reason_disposition(rows) == GATE_DISPOSITION_REVIEW


def test_final_surface_core_failure_remains_publication_stopping():
    rows = _reader(
        "reader_value_review:dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)",
        "reader_value_review:final_surface_summary_jargon_cluster (なぜ重要？/結論は？)",
    )
    assert rows[0]["severity"] == GATE_SEVERITY_SOFT
    assert rows[1]["severity"] == GATE_SEVERITY_REVIEW
    assert gate_reason_disposition(rows) == GATE_DISPOSITION_REVIEW


def test_unknown_reader_reason_fails_closed_to_review():
    rows = _reader("reader_value_review:new_unclassified_reader_failure")
    assert rows[0]["severity"] == GATE_SEVERITY_REVIEW
    assert gate_reason_disposition(rows) == GATE_DISPOSITION_REVIEW


def test_repetitive_insight_is_style_quality_not_publication_safety():
    rows = _reader("reader_value_review:repetitive_insight")
    assert rows[0]["severity"] == GATE_SEVERITY_SOFT
    assert gate_reason_disposition(rows) == GATE_DISPOSITION_PASS_WITH_WARNINGS


def test_fact_failure_still_dominates_style_only_reader_warning():
    rows = map_gate_reasons("fact", ["unsupported numeric claim: 44 minutes"]) + _reader(
        "reader_value_review:dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)"
    )
    assert rows[0]["severity"] == GATE_SEVERITY_HARD
    assert rows[1]["severity"] == GATE_SEVERITY_SOFT
    assert gate_reason_disposition(rows) == GATE_DISPOSITION_BLOCK


def test_fabricated_experience_remains_hard_block():
    rows = map_gate_reasons("human_appeal", ["fabricated_personal_experience"])
    assert rows[0]["severity"] == GATE_SEVERITY_HARD
    assert gate_reason_disposition(rows) == GATE_DISPOSITION_BLOCK


def test_run51_observed_reader_sets_yield_only_one_safe_style_candidate():
    # Candidate 1: multi-axis + explicit non-engineer core failure -> hold.
    candidate_1 = _reader(
        "reader_value_review:multi_axis_reader_weakness (accessibility/curiosity_pull/reader_enjoyment/jargon_translation/non_engineer_core_clarity)",
        "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)",
    )
    # Candidate 3: density + multi-axis + non-engineer core + final-surface failure -> hold.
    candidate_3 = _reader(
        "reader_value_review:dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)",
        "reader_value_review:multi_axis_reader_weakness (accessibility/curiosity_pull/reader_enjoyment/narrative_pull/jargon_translation/non_engineer_core_clarity/information_budget/reader_temperature_rhythm)",
        "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)",
        "reader_value_review:final_surface_summary_jargon_cluster (なぜ重要？/結論は？)",
    )
    # Candidate 5: density/style axes only -> warning, not a core-comprehension stop.
    candidate_5 = _reader(
        "reader_value_review:dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)",
        "reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/narrative_pull/information_budget/reader_temperature_rhythm)",
    )

    dispositions = [
        gate_reason_disposition(candidate_1),
        gate_reason_disposition(candidate_3),
        gate_reason_disposition(candidate_5),
    ]
    assert dispositions == [
        GATE_DISPOSITION_REVIEW,
        GATE_DISPOSITION_REVIEW,
        GATE_DISPOSITION_PASS_WITH_WARNINGS,
    ]
