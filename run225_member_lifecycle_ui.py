#!/usr/bin/env python3
"""Run225 member-surface overlay for active Stock lifecycle.

The authoritative member sync remains Run219/Run215. This zero-model overlay now
uses the existing lifecycle policy for both member visibility and homepage order:
- Archive items are withheld from the member presentation surface, but never deleted
  from Technology Intelligence / Decision History.
- A later first-party update or review recomputes the lifecycle and can restore the
  same canonical entity to the member surface.
- Fresh/Evergreen are ranked first.
- Aging can fill remaining homepage slots after active-current choices.

Important integration boundary: Run170-Run215 wrap ``member_presentation_sync``
source-state generation to preserve current copy authority. Run225 therefore wraps
the fully prepared source state only after those layers are installed; it never
reimplements or bypasses their copy/authority logic.

Current score, decision, Evidence, source copy and internal Notion records are untouched.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable

import member_presentation_sync as presentation
import run219_member_human_language_ui as run219
import run225_stock_lifecycle as lifecycle

_INSTALLED = False
_ORIGINAL_ASSIGN_HOME_RANKS = presentation.assign_home_ranks
_SOURCE_STATE_DELEGATE: Callable[[dict], dict[str, Any] | None] | None = None


def _ensure_lifecycle(state: dict[str, Any]) -> str:
    existing = str(state.get("stock_lifecycle") or "").strip()
    if existing in {lifecycle.FRESH, lifecycle.AGING, lifecycle.EVERGREEN, lifecycle.ARCHIVE}:
        return existing
    decision = lifecycle.classify_lifecycle(
        source=state.get("sources") or (),
        reviewed_at=state.get("last_reviewed"),
        analyzed_at=state.get("first_seen"),
        name=str(state.get("name") or ""),
        summary=str(state.get("topic") or state.get("plain_summary") or ""),
    )
    state["stock_lifecycle"] = decision.label
    state["stock_lifecycle_reason"] = decision.reason
    return decision.label


def member_visible_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return only lifecycle-current records for the paid member presentation.

    Archive is a presentation decision only.  The caller/source record is left in
    the internal Technology/History stores.  Because lifecycle classification is
    recomputed from the newest review anchor, a later fresh review naturally makes
    the canonical entity visible again without a second lifecycle implementation.
    """
    if not state:
        return None
    return None if _ensure_lifecycle(state) == lifecycle.ARCHIVE else state


def _source_state_with_lifecycle(page: dict) -> dict[str, Any] | None:
    delegate = _SOURCE_STATE_DELEGATE
    if delegate is None:
        raise RuntimeError("Run225 member lifecycle source-state delegate is not installed")
    return member_visible_state(delegate(page))


def assign_home_ranks_with_lifecycle(
    states: list[dict[str, Any]], *, limit: int = presentation.MEMBER_HOME_MAX
) -> list[dict[str, Any]]:
    """Preserve the existing ranker inside lifecycle priority bands."""
    for state in states:
        state["rank"] = None

    current: list[dict[str, Any]] = []
    aging: list[dict[str, Any]] = []
    for state in states:
        label = _ensure_lifecycle(state)
        if label in {lifecycle.FRESH, lifecycle.EVERGREEN}:
            current.append(state)
        elif label == lifecycle.AGING:
            aging.append(state)
        # Archive is intentionally absent from active recommendation lists.

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
    global _INSTALLED, _SOURCE_STATE_DELEGATE
    if _INSTALLED:
        return
    # Capture the already-installed Run170-Run215 authority chain and delegate to
    # it first.  Run225 only makes the final lifecycle visibility decision.
    _SOURCE_STATE_DELEGATE = presentation._source_state
    presentation._source_state = _source_state_with_lifecycle
    presentation.assign_home_ranks = assign_home_ranks_with_lifecycle
    _INSTALLED = True


def run_presentation_sync() -> dict[str, Any]:
    install()
    result = run219.run_presentation_sync()
    result["run225_stock_lifecycle"] = {
        "archive_excluded_from_member_surface": True,
        "fresh_evergreen_before_aging": True,
        "source_state_authority_preserved": True,
        "internal_records_deleted": 0,
    }
    result["zero_gemini_calls"] = True
    return result


def run_body_sync() -> dict[str, Any]:
    # Body rendering remains exactly Run219; visibility is owned by presentation sync.
    result = run219.run_body_sync()
    result["run225_stock_lifecycle"] = "presentation_visibility_only"
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
