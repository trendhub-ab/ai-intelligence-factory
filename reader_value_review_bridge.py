"""Run169 Reader Value Review Bridge.

This policy layer closes a production gap where zero-API reader diagnostics could flag
an article as dense/dry while Human Appeal still returned ACCEPTABLE and the article
shipped READY.

Design constraints:
- never weaken Fact/Evidence gates;
- never turn reader-value defects into HARD/Quality Failed;
- route only high-confidence reader-value defects to Needs Editorial Review;
- do not spend a Gemini Quality Retry when reader value is the only REVIEW reason;
- calm, technically serious prose remains publishable when it does not match the
  material-failure cluster.
"""
from __future__ import annotations

from typing import Any

READER_VALUE_MARKER = "reader_value_review:"
_INSTALLED_ATTR = "_run169_reader_value_review_bridge_installed"


def _material_reader_value_issues(pipeline_module: Any, article: str) -> list[str]:
    """Return only high-confidence reader-value failures from existing 0-API signals."""
    if not article:
        return []
    signals = pipeline_module._reader_experience_signals(article)
    issues: list[str] = []

    # Real-production closure: the 2026-08-29 READY set repeatedly showed this exact
    # combination. One weak stylistic signal is not enough; all four must agree.
    dense_report_cluster = all(
        signals.get(key) == "REVIEW"
        for key in (
            "reader_enjoyment",
            "narrative_pull",
            "information_budget",
            "reader_temperature_rhythm",
        )
    )
    if dense_report_cluster:
        issues.append(
            READER_VALUE_MARKER
            + "dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)"
        )

    # These are already explicit severe failure modes in the existing reader diagnostics.
    # They are safe to bridge because they describe structural failure, not a preference
    # for jokes, analogies, conversational phrases, or a specific editorial tone.
    severe_flags = (
        ("warm_hook_cold_body", "warm_hook_cold_body"),
        ("analogy_substance_thin", "analogy_substance_thin"),
        ("reader_delight_overclaim", "reader_delight_overclaim"),
        ("repetitive_insight", "repetitive_insight"),
    )
    for key, label in severe_flags:
        if bool(signals.get(key)):
            issues.append(READER_VALUE_MARKER + label)

    return list(dict.fromkeys(issues))


def _row_is_reader_value(row: dict) -> bool:
    message = str(row.get("message") or row.get("reason") or "")
    return READER_VALUE_MARKER in message


def install(pipeline_module: Any) -> Any:
    """Install the policy bridge onto an imported pipeline module, idempotently."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_human_appeal = pipeline_module.validate_human_appeal_gate
    original_retry = pipeline_module.should_attempt_dynamic_retry

    def validate_human_appeal_gate_with_reader_value(parsed: dict, peer_articles=None):
        state, issues = original_human_appeal(parsed, peer_articles)
        issues = list(issues or [])
        reader_issues = _material_reader_value_issues(
            pipeline_module,
            str((parsed or {}).get("note_draft") or ""),
        )
        if reader_issues:
            issues.extend(x for x in reader_issues if x not in issues)
            # Existing caller maps non-ACCEPTABLE Human Appeal to warning/review rows.
            # Do not introduce a new hard-fail state.
            if state == "ACCEPTABLE":
                state = "WEAK"
        return state, issues

    def should_attempt_dynamic_retry_without_reader_only_spend(
        reason_rows: list[dict], evidence_result: dict | None, candidate_origin: str = "new"
    ):
        rows = list(reason_rows or [])
        reader_rows = [row for row in rows if _row_is_reader_value(row)]
        if reader_rows:
            non_reader_blocking = [
                row
                for row in rows
                if not _row_is_reader_value(row)
                and row.get("severity")
                in {
                    getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"),
                    getattr(pipeline_module, "GATE_SEVERITY_REVIEW", "REVIEW"),
                }
            ]
            if not non_reader_blocking:
                return False, "reader_value_review_no_retry"
        return original_retry(rows, evidence_result, candidate_origin)

    pipeline_module.validate_human_appeal_gate = validate_human_appeal_gate_with_reader_value
    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_without_reader_only_spend
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module


def main() -> None:
    import pipeline

    install(pipeline)
    pipeline.main()


if __name__ == "__main__":
    main()
