"""Offline publish-yield diagnostics without changing production decisions.

This module is intentionally read-only and deterministic.  It consumes gate records that were
already produced by the pipeline and estimates a *diagnostic ceiling*: records held back only by
Human Appeal REVIEW reasons, while preserving every current HARD_BLOCK as blocked.

It does not call providers, Notion, note, GitHub, or any network service, and it never promotes a
record to Ready.  The ceiling is evidence for redesign decisions, not publication authorization.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from gate_reasoning import (
    GATE_SEVERITY_HARD,
    GATE_SEVERITY_REVIEW,
    GATE_SEVERITY_SOFT,
    normalize_gate_reason_rows,
)

CATEGORY_CURRENT_READY = "current_ready"
CATEGORY_SAFETY_BLOCKED = "safety_blocked"
CATEGORY_HUMAN_APPEAL_ONLY = "human_appeal_only"
CATEGORY_OTHER_REVIEW = "other_review"


def _reason_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows = record.get("reason_rows")
    if rows is None:
        rows = record.get("reason_codes")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _is_ready(record: dict[str, Any]) -> bool:
    status = record.get("final_status", record.get("status", ""))
    return str(status or "").strip().lower() == "ready"


def classify_candidate(record: dict[str, Any]) -> str:
    """Classify one existing result conservatively without mutating it.

    Safety is dominant.  Any HARD_BLOCK remains blocked even if the stored status says Ready.
    A non-Ready record is Human-Appeal-only only when every supplied reason belongs to the
    human_appeal gate and at least one reason is REVIEW severity.  Missing/unknown/mixed reasons
    fall back to other_review rather than being treated as recoverable.
    """

    rows = normalize_gate_reason_rows(_reason_rows(record))
    severities = {str(row.get("severity") or "") for row in rows}

    if GATE_SEVERITY_HARD in severities:
        return CATEGORY_SAFETY_BLOCKED

    if _is_ready(record):
        if any(severity == GATE_SEVERITY_REVIEW for severity in severities):
            return CATEGORY_OTHER_REVIEW
        return CATEGORY_CURRENT_READY

    if not rows:
        return CATEGORY_OTHER_REVIEW

    human_only = all(
        str(row.get("gate") or "") == "human_appeal"
        and str(row.get("severity") or "") in {GATE_SEVERITY_REVIEW, GATE_SEVERITY_SOFT}
        for row in rows
    )
    has_review = any(str(row.get("severity") or "") == GATE_SEVERITY_REVIEW for row in rows)
    if human_only and has_review:
        return CATEGORY_HUMAN_APPEAL_ONLY

    return CATEGORY_OTHER_REVIEW


def evaluate_publish_yield(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return current yield and a Human-Appeal-only diagnostic ceiling.

    ``recoverable_ceiling_*`` answers only this counterfactual question:
    "If Human-Appeal-only REVIEWs stopped being publication-stopping, while every HARD_BLOCK and
    all other review classes stayed unchanged, how many records could at most move forward?"

    It deliberately does not say those records *should* be Ready.
    """

    materialized = list(records)
    categories = [classify_candidate(record) for record in materialized]
    total = len(materialized)

    def count(category: str) -> int:
        return sum(value == category for value in categories)

    current_ready = count(CATEGORY_CURRENT_READY)
    safety_blocked = count(CATEGORY_SAFETY_BLOCKED)
    human_appeal_only = count(CATEGORY_HUMAN_APPEAL_ONLY)
    other_review = count(CATEGORY_OTHER_REVIEW)
    ceiling = current_ready + human_appeal_only

    return {
        "diagnostic_only": True,
        "total_count": total,
        "current_ready_count": current_ready,
        "current_ready_yield": (current_ready / total) if total else 0.0,
        "safety_blocked_count": safety_blocked,
        "human_appeal_only_count": human_appeal_only,
        "other_review_count": other_review,
        "recoverable_ceiling_count": ceiling,
        "recoverable_ceiling_yield": (ceiling / total) if total else 0.0,
        "categories": categories,
    }


def _load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
        records = payload["records"]
    else:
        raise ValueError("input must be a JSON list or an object with a records list")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("every record must be a JSON object")
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline publish-yield replay diagnostics")
    parser.add_argument("input", type=Path, help="JSON list, or object containing records[]")
    args = parser.parse_args(argv)
    print(json.dumps(evaluate_publish_yield(_load_records(args.input)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
