"""Metrics-only guardrail for observing Ready yield after naturalness changes.

This module has deliberately no publication or Ready-blocking authority.  It does
not define a threshold: thresholds must come from an evidence-backed benchmark,
not from implementation convenience.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def compute_ready_yield_metrics(outcomes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
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
