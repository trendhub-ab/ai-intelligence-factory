#!/usr/bin/env python3
"""Guarded one-shot migration for Run238 Deep Dive portfolio extraction."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "pipeline.py"

TARGET_FUNCTIONS = [
    "_topic_counts",
    "_apply_content_portfolio_balance",
    "publication_probability_score",
    "_apply_publication_reliability_slot",
    "_select_stocked_deep_dive_candidates",
]
NEXT_FUNCTION = "_deferred_ttl_days"

IMPORT_ANCHOR = '''from product_delivery_maintenance import (\n    current_month_id as _current_month_id_impl,\n    previous_month_id as _previous_month_id_impl,\n    run_evidence_health_maintenance as _run_evidence_health_maintenance_impl,\n    run_product_delivery_maintenance as _run_product_delivery_maintenance_impl,\n)\n'''

IMPORT_BLOCK = '''from deep_dive_portfolio import (\n    apply_content_portfolio_balance as _apply_content_portfolio_balance_impl,\n    apply_publication_reliability_slot as _apply_publication_reliability_slot_impl,\n    publication_probability_score as _publication_probability_score_impl,\n    select_stocked_deep_dive_candidates as _select_stocked_deep_dive_candidates_impl,\n    topic_counts as _topic_counts_impl,\n)\n'''

WRAPPERS = '''def _topic_counts(items: list[dict]) -> dict[str, int]:\n    \"\"\"Bind canonical Run238 topic counting to the live topic normalizer.\"\"\"\n    return _topic_counts_impl(items, normalize_portfolio_topic=normalize_portfolio_topic)\n\n\ndef _apply_content_portfolio_balance(ordered: list[dict], visible_slots: int) -> list[dict]:\n    \"\"\"Bind canonical Run238 balance logic to live portfolio configuration.\"\"\"\n    return _apply_content_portfolio_balance_impl(\n        ordered,\n        visible_slots,\n        enabled=ENABLE_PORTFOLIO_BALANCE,\n        min_distinct_topics=PORTFOLIO_MIN_DISTINCT_TOPICS,\n        priority_tolerance=PORTFOLIO_TOPIC_PRIORITY_TOLERANCE,\n        evergreen_portfolio_min=EVERGREEN_PORTFOLIO_MIN,\n        normalize_portfolio_topic=normalize_portfolio_topic,\n    )\n\n\ndef publication_probability_score(item: dict) -> int:\n    \"\"\"Compatibility wrapper for the canonical Run238 metadata proxy.\"\"\"\n    return _publication_probability_score_impl(item)\n\n\ndef _apply_publication_reliability_slot(ordered: list[dict], visible_slots: int) -> list[dict]:\n    \"\"\"Bind canonical Run238 reliability-slot logic to live configuration.\"\"\"\n    return _apply_publication_reliability_slot_impl(\n        ordered,\n        visible_slots,\n        enabled=ENABLE_PUBLICATION_RELIABILITY_SLOT,\n        reliability_slots=PUBLICATION_RELIABILITY_SLOTS,\n        min_decision_score=PUBLICATION_RELIABILITY_MIN_DECISION_SCORE,\n        min_advantage=PUBLICATION_RELIABILITY_MIN_ADVANTAGE,\n        logger=logger,\n    )\n\n\ndef _select_stocked_deep_dive_candidates(screened: list[dict]) -> list[dict]:\n    \"\"\"Bind canonical Run238 Stock ordering to live pipeline policies.\"\"\"\n    return _select_stocked_deep_dive_candidates_impl(\n        screened,\n        notion_save_threshold_score=NOTION_SAVE_THRESHOLD_SCORE,\n        attach_profit_metadata=_attach_profit_metadata,\n        attach_portfolio_topic=_attach_portfolio_topic,\n        enable_profit_priority=ENABLE_PROFIT_PRIORITY,\n        profit_score_neutral=PROFIT_SCORE_NEUTRAL,\n        top_n_for_deep_dive=TOP_N_FOR_DEEP_DIVE,\n        evergreen_portfolio_min=EVERGREEN_PORTFOLIO_MIN,\n        evergreen_priority_tolerance=EVERGREEN_PRIORITY_TOLERANCE,\n        apply_content_portfolio_balance_fn=_apply_content_portfolio_balance,\n        apply_publication_reliability_slot_fn=_apply_publication_reliability_slot,\n    )\n\n\n'''


def _top_level_functions(source: str):
    tree = ast.parse(source)
    return [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def transform_source(source: str) -> str:
    if IMPORT_BLOCK in source and all(
        f"def {name}" in source for name in TARGET_FUNCTIONS
    ):
        # Continue to validate wrapper ownership below; do not silently re-apply.
        pass
    elif IMPORT_BLOCK not in source:
        if source.count(IMPORT_ANCHOR) != 1:
            raise RuntimeError("Run238 import anchor missing or ambiguous")
        source = source.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_BLOCK, 1)

    functions = _top_level_functions(source)
    by_name = {node.name: node for node in functions}
    missing = [name for name in TARGET_FUNCTIONS + [NEXT_FUNCTION] if name not in by_name]
    if missing:
        raise RuntimeError(f"Run238 target surface missing: {missing}")

    start = by_name[TARGET_FUNCTIONS[0]]
    end = by_name[NEXT_FUNCTION]
    between = [
        node.name
        for node in functions
        if start.lineno <= node.lineno < end.lineno
    ]
    if between != TARGET_FUNCTIONS:
        # If already migrated, validate thin wrappers by canonical delegate markers.
        required_markers = [
            "return _topic_counts_impl(",
            "return _apply_content_portfolio_balance_impl(",
            "return _publication_probability_score_impl(item)",
            "return _apply_publication_reliability_slot_impl(",
            "return _select_stocked_deep_dive_candidates_impl(",
        ]
        if between == TARGET_FUNCTIONS and all(marker in source for marker in required_markers):
            return source
        raise RuntimeError(f"Run238 unexpected function adjacency: {between}")

    start_idx = sum(len(line) for line in source.splitlines(keepends=True)[: start.lineno - 1])
    end_idx = sum(len(line) for line in source.splitlines(keepends=True)[: end.lineno - 1])
    old_block = source[start_idx:end_idx]

    required_old_markers = [
        "counts: dict[str, int] = {}",
        "PORTFOLIO_TOPIC_PRIORITY_TOLERANCE",
        "urlparse(url).hostname",
        "PUBLICATION_RELIABILITY_MIN_ADVANTAGE",
        "eligible = [",
        "EVERGREEN_PRIORITY_TOLERANCE",
    ]
    if not all(marker in old_block for marker in required_old_markers):
        # A subsequent idempotent invocation should see the wrapper block instead.
        if all(marker in old_block for marker in (
            "_topic_counts_impl",
            "_apply_content_portfolio_balance_impl",
            "_publication_probability_score_impl",
            "_apply_publication_reliability_slot_impl",
            "_select_stocked_deep_dive_candidates_impl",
        )):
            return source
        raise RuntimeError("Run238 old algorithm markers changed; refusing migration")

    migrated = source[:start_idx] + WRAPPERS + source[end_idx:]
    ast.parse(migrated)
    return migrated


def main() -> int:
    before = PIPELINE.read_text(encoding="utf-8")
    after = transform_source(before)
    if after == before:
        print("Run238 migration already applied; no changes")
        return 0
    PIPELINE.write_text(after, encoding="utf-8")
    print(
        "Run238 pipeline migration applied: "
        f"lines {len(before.splitlines())} -> {len(after.splitlines())}; "
        f"bytes {len(before.encode('utf-8'))} -> {len(after.encode('utf-8'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
