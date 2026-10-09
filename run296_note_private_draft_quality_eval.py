#!/usr/bin/env python3
"""Read-only quality evaluation for remaining unpublished note drafts.

This module reuses the Run296 inventory/browser contract and emits only aggregate
quality diagnostics. It never emits unpublished title/body, draft URL, draft ID,
or content fingerprints and performs no note mutation, publication, or model call.
"""
from __future__ import annotations

from collections import Counter
import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import editorial_naturalness
import reader_experience_signals
import run296_note_private_draft_inventory as inventory

CONFIRM_TOKEN = inventory.CONFIRM_TOKEN


def _opening_excerpt(value: str, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[: max(0, int(limit))]


def _safe_list(value: Any) -> list[str]:
    return [str(item) for item in (value or []) if str(item)]


def quality_diagnostics(text: str) -> dict[str, Any]:
    """Return only categorical/count diagnostics; never return article text."""
    body = str(text or "")
    natural = editorial_naturalness.ai_style_composite_signals(body, [])
    depth = editorial_naturalness.human_editorial_depth_signals(body)
    reader = reader_experience_signals.reader_experience_signals(body, _opening_excerpt)
    claims = editorial_naturalness.classify_article_claims(
        {"note_draft": body, "action_text": ""}
    )

    actions: list[str] = []
    if int(natural.get("generic_business_scaffold_count") or 0) >= 4:
        actions.append("rewrite_generic_business_scaffold")
    if bool(natural.get("generic_collective_opening")):
        actions.append("replace_generic_collective_opening")
    if bool(natural.get("editorial_register_dense")):
        actions.append("reduce_editorial_register")
    if int(natural.get("explanatory_ending_count") or 0) >= 3:
        actions.append("vary_explanatory_endings")
    if bool(natural.get("uniform_sections")):
        actions.append("vary_section_rhythm")
    if bool(depth.get("high")):
        actions.append("compress_repetition_and_transitions")
    if str(reader.get("accessibility") or "REVIEW") != "GOOD":
        actions.append("improve_reader_accessibility")
    if str(reader.get("curiosity_pull") or "REVIEW") != "GOOD":
        actions.append("strengthen_article_specific_opening")
    if str(reader.get("narrative_pull") or "REVIEW") != "GOOD":
        actions.append("break_long_explanatory_runs")
    if str(reader.get("return_pull") or "REVIEW") != "GOOD":
        actions.append("strengthen_decision_close")

    reader_review_count = sum(
        1
        for key in (
            "accessibility",
            "curiosity_pull",
            "reader_enjoyment",
            "return_pull",
            "narrative_pull",
        )
        if str(reader.get(key) or "REVIEW") != "GOOD"
    )
    if bool(natural.get("high")) or bool(depth.get("high")):
        repair_priority = "HIGH"
    elif reader_review_count >= 2:
        repair_priority = "MEDIUM"
    else:
        repair_priority = "LOW"

    return {
        "naturalness_score": int(natural.get("score") or 0),
        "naturalness_high": bool(natural.get("high")),
        "glue_total": int(natural.get("glue_total") or 0),
        "repeated_glue": bool(natural.get("repeated_glue")),
        "point_ending_count": int(natural.get("point_ending_count") or 0),
        "contrast_count": int(natural.get("contrast_count") or 0),
        "enum_count": int(natural.get("enum_count") or 0),
        "short_burst": bool(natural.get("short_burst")),
        "uniform_sections": bool(natural.get("uniform_sections")),
        "generic_business_scaffold_count": int(natural.get("generic_business_scaffold_count") or 0),
        "generic_collective_opening": bool(natural.get("generic_collective_opening")),
        "editorial_register_count": int(natural.get("editorial_register_count") or 0),
        "editorial_register_distinct": int(natural.get("editorial_register_distinct") or 0),
        "editorial_register_dense": bool(natural.get("editorial_register_dense")),
        "ordinal_framing_count": int(natural.get("ordinal_framing_count") or 0),
        "evaluative_register_count": int(natural.get("evaluative_register_count") or 0),
        "explanatory_ending_count": int(natural.get("explanatory_ending_count") or 0),
        "staged_framing_count": int(natural.get("staged_framing_count") or 0),
        "invitational_close_count": int(natural.get("invitational_close_count") or 0),
        "human_depth_score": int(depth.get("score") or 0),
        "human_depth_high": bool(depth.get("high")),
        "near_duplicate_pairs": int(depth.get("near_duplicate_pairs") or 0),
        "transition_total": int(depth.get("transition_total") or 0),
        "repeated_transition": bool(depth.get("repeated_transition")),
        "human_explanatory_closer_count": int(depth.get("explanatory_closer_count") or 0),
        "reader_accessibility": str(reader.get("accessibility") or "REVIEW"),
        "reader_curiosity_pull": str(reader.get("curiosity_pull") or "REVIEW"),
        "reader_enjoyment": str(reader.get("reader_enjoyment") or "REVIEW"),
        "reader_return_pull": str(reader.get("return_pull") or "REVIEW"),
        "reader_narrative_pull": str(reader.get("narrative_pull") or "REVIEW"),
        "article_specific_angle": str(reader.get("article_specific_angle") or "UNKNOWN"),
        "information_budget": str(reader.get("information_budget") or "UNKNOWN"),
        "accessibility_issues": _safe_list(reader.get("accessibility_issues")),
        "enjoyment_issues": _safe_list(reader.get("enjoyment_issues")),
        "technical_terms_per_1000_chars": float(reader.get("technical_terms_per_1000_chars") or 0.0),
        "claim_fact_signals": int(claims.get("fact") or 0),
        "claim_interpretation_signals": int(claims.get("interpretation") or 0),
        "claim_observation_signals": int(claims.get("observation") or 0),
        "claim_decision_signals": int(claims.get("decision") or 0),
        "reader_review_count": int(reader_review_count),
        "repair_priority": repair_priority,
        "recommended_actions": list(dict.fromkeys(actions)),
    }


def _safe_repair_record(row: dict[str, Any]) -> dict[str, Any]:
    body = str(row.get("body") or "")
    return {
        "position": int(row.get("position") or 0),
        "title_chars": int(row.get("title_chars") or 0),
        "body_chars": int(row.get("body_chars") or 0),
        "eyecatch_present": bool(row.get("eyecatch_present")),
        "current_aiif_linked": bool(row.get("current_aiif_linked")),
        "classification": str(row.get("classification") or "REPAIR"),
        "reasons": _safe_list(row.get("reasons")),
        "quality": quality_diagnostics(body),
    }


def run(*, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise inventory.InventoryError("confirmation_invalid")

    tracked_ids = inventory._tracked_draft_ids()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise inventory.InventoryError("playwright_missing") from exc

    raw_records: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        context = inventory.run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            routes = inventory._discover_all_draft_routes(context, page)
            for position, route in enumerate(routes, start=1):
                try:
                    raw_records.append(
                        inventory._inspect_one(page, route, position=position, tracked_ids=tracked_ids)
                    )
                except inventory.InventoryError as exc:
                    if exc.code == "note_auth_inactive":
                        raise
                    raw_records.append(
                        {
                            "position": position,
                            "title_chars": 0,
                            "body_chars": 0,
                            "eyecatch_present": False,
                            "current_aiif_linked": False,
                            "classification": "REPAIR",
                            "reasons": [f"inspection_failed:{exc.code}"],
                            "body": "",
                        }
                    )
        finally:
            context.close()

    inspectable = [row for row in raw_records if "body_fingerprint" in row]
    inventory._mark_exact_duplicates(inspectable)
    inventory._classify_records(inspectable)

    repair_rows = [row for row in raw_records if str(row.get("classification") or "") == "REPAIR"]
    safe_repairs = [_safe_repair_record(row) for row in repair_rows]
    priorities = Counter((row.get("quality") or {}).get("repair_priority") for row in safe_repairs)
    return {
        "success": True,
        "status": "quality_evaluation_complete",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "private_content_exposed": False,
        "total_remaining_drafts": len(raw_records),
        "repair_candidates": len(safe_repairs),
        "repair_priority_counts": {
            "HIGH": int(priorities.get("HIGH", 0)),
            "MEDIUM": int(priorities.get("MEDIUM", 0)),
            "LOW": int(priorities.get("LOW", 0)),
        },
        "records": safe_repairs,
    }


def _safe_failure(code: str) -> dict[str, Any]:
    return {
        "success": False,
        "status": "fail_closed",
        "diagnostic_code": str(code),
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "private_content_exposed": False,
        "records": [],
    }


def _write_result(path_value: str, result: dict[str, Any]) -> None:
    if not path_value:
        return
    target = Path(path_value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", default=os.environ.get("NOTE_INVENTORY_CONFIRM", ""))
    parser.add_argument("--result-file", default=os.environ.get("NOTE_QUALITY_RESULT_FILE", ""))
    args = parser.parse_args()

    exit_code = 0
    try:
        result = run(confirm=args.confirm)
    except inventory.InventoryError as exc:
        result = _safe_failure(exc.code)
        exit_code = 2
    except Exception:
        result = _safe_failure("unexpected_quality_evaluation_failure")
        exit_code = 2

    _write_result(args.result_file, result)
    print(json.dumps(result, ensure_ascii=False))
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
