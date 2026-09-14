from gate_reasoning import (
    GATE_DISPOSITION_BLOCK,
    GATE_DISPOSITION_PASS_WITH_WARNINGS,
    GATE_DISPOSITION_REVIEW,
    gate_reason_disposition,
    map_gate_reasons,
)


def _rows(*pairs):
    rows = []
    for gate, messages in pairs:
        rows.extend(map_gate_reasons(gate, list(messages)))
    return rows


def test_run51_policy_replay_restores_two_safe_publish_candidates_without_passing_hard_failures():
    """Replay the final Run51 gate outcomes against the current editorial policy.

    This is intentionally a zero-provider policy replay, not a generation benchmark. It protects
    the business-critical lower bound established after Run354/356: style/readability debt may
    publish with warnings, core-comprehension debt stays in review, and Fact/Evidence failures
    remain blocked.
    """
    cases = {
        # Run356 removes the false core-comprehension markers for the Show HN draft because its
        # Japanese↔technical inline glosses are valid reader bridges. The remaining axes are
        # editorial quality debt, not a publication stop.
        "show_hn_agent_team": _rows(
            (
                "human_appeal",
                (
                    "reader_value_review:multi_axis_reader_weakness "
                    "(accessibility/curiosity_pull/reader_enjoyment)",
                ),
            ),
        ),
        # Historical Run51 reasons: dense report / rhythm / information-budget weakness only.
        "malleable_software": _rows(
            (
                "human_appeal",
                (
                    "reader_value_review:dense_report_cluster "
                    "(Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)",
                    "reader_value_review:multi_axis_reader_weakness "
                    "(accessibility/reader_enjoyment/narrative_pull/information_budget/reader_temperature_rhythm)",
                ),
            ),
        ),
        # OpenArch still fails the core-understanding boundary; Run356 must not hide real jargon debt.
        "openarch": _rows(
            (
                "human_appeal",
                (
                    "reader_value_review:dense_report_cluster "
                    "(Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)",
                    "reader_value_review:multi_axis_reader_weakness "
                    "(accessibility/curiosity_pull/reader_enjoyment/narrative_pull/jargon_translation/"
                    "non_engineer_core_clarity/information_budget/reader_temperature_rhythm)",
                    "reader_value_review:non_engineer_access_failure "
                    "(Accessibility/Jargon Translation/Non-Engineer Core Clarity)",
                ),
            ),
        ),
        # Run51 hard Fact failures must remain blocked regardless of editorial policy changes.
        "claude_cipher": _rows(
            (
                "fact",
                (
                    "unsupported numeric claim: 44分",
                    "causal inference overclaim: observational evidence upgraded to causation",
                ),
            ),
        ),
        "ask_hn_mcp": _rows(
            (
                "fact",
                ("unsupported outcome extrapolation: ROI/financial outcome not measured by evidence",),
            ),
            (
                "evidence",
                ("PRIMARY_SOURCE_AUTHORITY_INSUFFICIENT: discovery source cannot establish decision authority",),
            ),
            (
                "publication",
                ("article_structure_needs_edit",),
            ),
        ),
    }

    dispositions = {name: gate_reason_disposition(rows) for name, rows in cases.items()}

    assert dispositions["show_hn_agent_team"] == GATE_DISPOSITION_PASS_WITH_WARNINGS
    assert dispositions["malleable_software"] == GATE_DISPOSITION_PASS_WITH_WARNINGS
    assert dispositions["openarch"] == GATE_DISPOSITION_REVIEW
    assert dispositions["claude_cipher"] == GATE_DISPOSITION_BLOCK
    assert dispositions["ask_hn_mcp"] == GATE_DISPOSITION_BLOCK

    publish_candidates = [
        name for name, disposition in dispositions.items()
        if disposition == GATE_DISPOSITION_PASS_WITH_WARNINGS
    ]
    assert publish_candidates == ["show_hn_agent_team", "malleable_software"]
    assert len(publish_candidates) / len(cases) == 0.4
