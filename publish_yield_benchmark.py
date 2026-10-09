"""Deterministic publish-yield policy benchmark for AIIF.

This benchmark is deliberately narrower than a live Daily run. It replays labelled gate-reason
sets through the *current* reason-code/severity policy and reports two things that matter to the
business at the same time:

1. safety/core-comprehension false passes must remain zero;
2. known style-only cases must not be held back as publication reviews.

The module has no provider, network, Notion, note, or persistence dependency. It does not promote
any stored article to Ready and must never be used as a publication authority. Its purpose is to
make future Gate/Reader redesigns prove that yield improved without buying that yield by weakening
Fact/Evidence/core-comprehension safety.
"""
from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from gate_reasoning import (
    GATE_DISPOSITION_BLOCK,
    GATE_DISPOSITION_PASS,
    GATE_DISPOSITION_PASS_WITH_WARNINGS,
    GATE_DISPOSITION_REVIEW,
    gate_reason_disposition,
    map_gate_reasons,
)

EXPECTED_PUBLISHABLE = "publishable"
EXPECTED_REVIEW = "review"
EXPECTED_BLOCK = "block"
_VALID_EXPECTED = {EXPECTED_PUBLISHABLE, EXPECTED_REVIEW, EXPECTED_BLOCK}
_PUBLISHABLE_DISPOSITIONS = {GATE_DISPOSITION_PASS, GATE_DISPOSITION_PASS_WITH_WARNINGS}


def _expected_for_disposition(disposition: str) -> str:
    if disposition in _PUBLISHABLE_DISPOSITIONS:
        return EXPECTED_PUBLISHABLE
    if disposition == GATE_DISPOSITION_REVIEW:
        return EXPECTED_REVIEW
    if disposition == GATE_DISPOSITION_BLOCK:
        return EXPECTED_BLOCK
    raise ValueError(f"unknown gate disposition: {disposition}")


def _reason_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw = case.get("reasons") or []
    if not isinstance(raw, list):
        raise ValueError("benchmark case reasons must be a list")
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("benchmark reason must be an object")
        gate = str(item.get("gate") or "").strip()
        message = str(item.get("message") or "").strip()
        if not gate or not message:
            raise ValueError("benchmark reason requires gate and message")
        rows.extend(map_gate_reasons(gate, [message]))
    return rows


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one labelled reason-set using current production reason policy."""
    expected = str(case.get("expected") or "").strip().lower()
    if expected not in _VALID_EXPECTED:
        raise ValueError(f"invalid expected outcome: {expected!r}")
    rows = _reason_rows(case)
    disposition = gate_reason_disposition(rows)
    actual = _expected_for_disposition(disposition)
    return {
        "id": str(case.get("id") or ""),
        "risk_class": str(case.get("risk_class") or "unspecified"),
        "expected": expected,
        "actual": actual,
        "disposition": disposition,
        "matched": actual == expected,
        "reason_rows": rows,
    }


def evaluate_benchmark(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return a business-facing scorecard without changing any production state."""
    results = [evaluate_case(dict(case)) for case in cases]
    total = len(results)
    publishable = sum(row["actual"] == EXPECTED_PUBLISHABLE for row in results)
    exact = sum(bool(row["matched"]) for row in results)

    safety_false_passes = [
        row for row in results
        if row["expected"] == EXPECTED_BLOCK and row["actual"] == EXPECTED_PUBLISHABLE
    ]
    core_false_passes = [
        row for row in results
        if row["expected"] == EXPECTED_REVIEW
        and row["actual"] == EXPECTED_PUBLISHABLE
        and row["risk_class"] in {"core_comprehension", "final_surface", "unknown_fail_closed"}
    ]
    unnecessary_holds = [
        row for row in results
        if row["expected"] == EXPECTED_PUBLISHABLE and row["actual"] != EXPECTED_PUBLISHABLE
    ]

    return {
        "benchmark_only": True,
        "zero_provider_calls": True,
        "total_count": total,
        "exact_match_count": exact,
        "exact_match_rate": (exact / total) if total else 0.0,
        "projected_publishable_count": publishable,
        "projected_publishable_yield": (publishable / total) if total else 0.0,
        "safety_false_pass_count": len(safety_false_passes),
        "core_false_pass_count": len(core_false_passes),
        "unnecessary_hold_count": len(unnecessary_holds),
        "safety_false_pass_ids": [row["id"] for row in safety_false_passes],
        "core_false_pass_ids": [row["id"] for row in core_false_passes],
        "unnecessary_hold_ids": [row["id"] for row in unnecessary_holds],
        "results": results,
    }


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def compute_ready_yield_metrics(outcomes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Measure yield loss without acquiring any authority to block publication.

    No threshold is defined here. A future threshold must be evidence-backed from a
    labelled corpus rather than invented as part of a style-detector implementation.
    """
    rows = [dict(row) for row in outcomes]
    total = len(rows)
    ready_count = sum(bool(row.get("ready")) for row in rows)
    hard_gate_block_count = sum(bool(row.get("hard_gate_blocked")) for row in rows)
    repair_rows = [row for row in rows if bool(row.get("naturalness_repair_attempted"))]
    retry_observed = [
        row for row in repair_rows
        if row.get("naturalness_retry_succeeded") is not None
    ]
    retry_success_count = sum(
        bool(row.get("naturalness_retry_succeeded")) for row in retry_observed
    )
    style_only_non_ready_count = sum(
        bool(row.get("style_only_non_ready")) and not bool(row.get("ready"))
        for row in rows
    )
    return {
        "total_candidates": total,
        "ready_count": ready_count,
        "ready_rate": _rate(ready_count, total),
        "hard_gate_block_count": hard_gate_block_count,
        "hard_gate_block_rate": _rate(hard_gate_block_count, total),
        "naturalness_repair_count": len(repair_rows),
        "naturalness_repair_rate": _rate(len(repair_rows), total),
        "naturalness_retry_success_count": retry_success_count,
        "naturalness_retry_success_rate": _rate(retry_success_count, len(retry_observed)),
        "style_only_non_ready_count": style_only_non_ready_count,
        "style_only_non_ready_rate": _rate(style_only_non_ready_count, total),
        "blocks_ready": False,
        "policy": "diagnostic_only",
    }


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("cases")
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("benchmark input must be a JSON list or an object containing cases[]")
    ids = [str(item.get("id") or "") for item in payload]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("benchmark case ids must be non-empty and unique")
    return [dict(item) for item in payload]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIIF zero-API publish-yield policy benchmark")
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    report = evaluate_benchmark(load_cases(args.input))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if (
        report["safety_false_pass_count"]
        or report["core_false_pass_count"]
        or report["unnecessary_hold_count"]
        or report["exact_match_count"] != report["total_count"]
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
