#!/usr/bin/env python3
"""Run225 member-surface overlay for active Stock lifecycle.

The authoritative member sync remains Run219/Run215.  This zero-model overlay
changes only recommendation eligibility/order:
- Archive items remain searchable/history records but receive no homepage rank.
- Fresh/Evergreen are ranked first.
- Aging can fill remaining homepage slots after active-current choices.

Current score, decision, Evidence, source copy and Notion records are untouched.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import member_presentation_sync as presentation
import run219_member_human_language_ui as run219
import run225_stock_lifecycle as lifecycle

_INSTALLED = False
_ORIGINAL_SOURCE_STATE = presentation._source_state
_ORIGINAL_ASSIGN_HOME_RANKS = presentation.assign_home_ranks


def _source_state_with_lifecycle(page: dict) -> dict[str, Any] | None:
    state = _ORIGINAL_SOURCE_STATE(page)
    if not state:
        return None
    decision = lifecycle.classify_lifecycle(
        source=state.get("sources") or (),
        reviewed_at=state.get("last_reviewed"),
        analyzed_at=state.get("first_seen"),
        name=str(state.get("name") or ""),
        summary=str(state.get("topic") or state.get("plain_summary") or ""),
    )
    state["stock_lifecycle"] = decision.label
    state["stock_lifecycle_reason"] = decision.reason
    return state


def assign_home_ranks_with_lifecycle(
    states: list[dict[str, Any]], *, limit: int = presentation.MEMBER_HOME_MAX
) -> list[dict[str, Any]]:
    for state in states:
        state["rank"] = None

    # Unknown lifecycle exists only for legacy/test callers and is treated as
    # Fresh for backward compatibility. Actual source rows are classified above.
    current = [
        state
        for state in states
        if state.get("stock_lifecycle", lifecycle.FRESH)
        in {lifecycle.FRESH, lifecycle.EVERGREEN}
    ]
    aging = [
        state
        for state in states
        if state.get("stock_lifecycle") == lifecycle.AGING
    ]
    # Archive is intentionally absent from both lists.
    selected = _ORIGINAL_ASSIGN_HOME_RANKS(current, limit=limit)
    slots = max(0, limit - len(selected))
    if slots:
        aging_selected = _ORIGINAL_ASSIGN_HOME_RANKS(aging, limit=slots)
        offset = len(selected)
        for index, state in enumerate(aging_selected, 1):
            state["rank"] = offset + index
        selected.extend(aging_selected)
    return selected


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    presentation._source_state = _source_state_with_lifecycle
    presentation.assign_home_ranks = assign_home_ranks_with_lifecycle
    _INSTALLED = True


def run_presentation_sync() -> dict[str, Any]:
    install()
    result = run219.run_presentation_sync()
    result["run225_stock_lifecycle"] = {
        "archive_excluded_from_homepage": True,
        "fresh_evergreen_before_aging": True,
        "records_deleted": 0,
    }
    result["zero_gemini_calls"] = True
    return result


def run_body_sync() -> dict[str, Any]:
    # Body rendering remains exactly Run219; lifecycle changes navigation only.
    result = run219.run_body_sync()
    result["run225_stock_lifecycle"] = "navigation_only"
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python run225_member_lifecycle_ui.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
