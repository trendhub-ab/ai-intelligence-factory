#!/usr/bin/env python3
"""Run212: recover reader-facing copy without reviving historical decision state.

Run201 intentionally moved old external Product Review JSON out of the active
root namespace.  Those files remain useful as reviewed writing evidence, but
must never become authoritative for current scores, judgments, risks, Evidence,
or product status.

This layer therefore reuses archived reviews only for two presentation fields:
- ``これは何？`` / ``plain_summary`` when the current value is the deterministic
  fallback produced by the member UX guard;
- ``今回の話題`` / ``topic_trigger`` when the current topic is generic.

Time-sensitive archived copy is rejected.  Current Decision Intelligence fields
remain authoritative.  No Gemini/model request is available in this module.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import member_human_language_ux as base
import member_human_language_ux_v2 as ux2
import member_ux_guard as guard


ACTIVE_REVIEW_ROOT = Path("external_reviews")
ARCHIVED_REVIEW_ROOT = Path(
    "docs/archive/repository-cleanup-2026-09-02/external-review-history"
)
ARCHIVE_COPY_KIND = "archive_copy_only"
ACTIVE_COPY_KIND = "active_review"

# Historical wording can remain factually true while its recency claim becomes
# false.  Reject the whole presentation fragment rather than trying to rewrite a
# date/freshness claim mechanically.
_STALE_ARCHIVE_COPY_RE = re.compile(
    r"(?:20\d{2}年\d{1,2}月(?:\d{1,2}日)?時点|"
    r"現時点|現在も(?:活発|継続|更新)|継続的に更新|"
    r"最新(?:版|情報|動向|状況))"
)

_ORIGINAL_LOAD_REVIEW_COPY_INDEX = base.load_review_copy_index
_ORIGINAL_HUMANIZE_STATE = base.humanize_state
_INSTALLED = False
_RUNTIME_STATS: dict[str, int] = {}


def reset_runtime_stats() -> None:
    _RUNTIME_STATS.clear()
    _RUNTIME_STATS.update(
        {
            "archive_matches": 0,
            "archive_summary_applied": 0,
            "archive_topic_applied": 0,
            "archive_summary_filtered_stale": 0,
            "archive_topic_filtered_stale": 0,
        }
    )


reset_runtime_stats()


def _safe_archive_fragment(value: Any, *, stat_key: str) -> str:
    text = base._clean(value)
    if not text:
        return ""
    if _STALE_ARCHIVE_COPY_RE.search(text):
        _RUNTIME_STATS[stat_key] += 1
        return ""
    return text


def _sanitize_archive_copy(copy: dict[str, Any]) -> dict[str, str]:
    """Expose only stable reader copy; never historical decision fields."""
    return {
        "plain_summary": _safe_archive_fragment(
            copy.get("plain_summary"), stat_key="archive_summary_filtered_stale"
        ),
        "topic_trigger": _safe_archive_fragment(
            copy.get("topic_trigger"), stat_key="archive_topic_filtered_stale"
        ),
        "short_rationale": "",
        "main_risk": "",
        "best_for": "",
        "avoid_for": "",
        "_source_kind": ARCHIVE_COPY_KIND,
    }


def _mark_active_copy(copy: dict[str, Any]) -> dict[str, Any]:
    out = dict(copy)
    out["_source_kind"] = ACTIVE_COPY_KIND
    return out


def _merge_index(
    older: dict[str, dict[str, dict[str, Any]]],
    newer: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Merge indexes so current active reviews always beat archived history."""
    result = {
        "by_url": dict(older.get("by_url") or {}),
        "by_name": dict(older.get("by_name") or {}),
    }
    result["by_url"].update(newer.get("by_url") or {})
    result["by_name"].update(newer.get("by_name") or {})
    return result


def load_combined_review_copy_index(
    root: str | Path = ACTIVE_REVIEW_ROOT,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Load active reviews plus copy-only archived history for the default path.

    Explicit non-default roots preserve the original Run170 behavior, which keeps
    existing tests/tools deterministic and prevents this compatibility layer from
    silently changing arbitrary replay jobs.
    """
    root_path = Path(root)
    if root_path != ACTIVE_REVIEW_ROOT:
        return _ORIGINAL_LOAD_REVIEW_COPY_INDEX(root_path)

    archive_raw = _ORIGINAL_LOAD_REVIEW_COPY_INDEX(ARCHIVED_REVIEW_ROOT)
    archive_safe = {
        "by_url": {
            key: _sanitize_archive_copy(value)
            for key, value in (archive_raw.get("by_url") or {}).items()
        },
        "by_name": {
            key: _sanitize_archive_copy(value)
            for key, value in (archive_raw.get("by_name") or {}).items()
        },
    }

    active_raw = _ORIGINAL_LOAD_REVIEW_COPY_INDEX(ACTIVE_REVIEW_ROOT)
    active = {
        "by_url": {
            key: _mark_active_copy(value)
            for key, value in (active_raw.get("by_url") or {}).items()
        },
        "by_name": {
            key: _mark_active_copy(value)
            for key, value in (active_raw.get("by_name") or {}).items()
        },
    }
    return _merge_index(archive_safe, active)


def _current_summary_is_guard_fallback(state: dict[str, Any]) -> bool:
    current = base._clean(state.get("plain_summary"))
    if not current:
        return True
    try:
        expected = base._clean(guard.fallback_summary(state))
    except Exception:
        return False
    return bool(expected and current == expected)


def safe_humanize_state(
    state: dict[str, Any], review_copy: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Allow archive copy to improve presentation without becoming current truth."""
    reviewed = dict(review_copy or {})
    if reviewed.get("_source_kind") != ARCHIVE_COPY_KIND:
        return _ORIGINAL_HUMANIZE_STATE(state, reviewed)

    _RUNTIME_STATS["archive_matches"] += 1
    before_summary = base._clean(state.get("plain_summary"))
    before_topic = base._clean(state.get("topic"))

    # A historical summary may replace only our own deterministic fallback.  A
    # current non-fallback summary wins even if the archived prose is nicer.
    if not _current_summary_is_guard_fallback(state):
        reviewed["plain_summary"] = ""

    # Defense in depth: these fields must stay empty for archived inputs even if a
    # future loader change accidentally reintroduces them.
    for key in ("short_rationale", "main_risk", "best_for", "avoid_for"):
        reviewed[key] = ""

    out = _ORIGINAL_HUMANIZE_STATE(state, reviewed)
    if reviewed.get("plain_summary") and base._clean(out.get("plain_summary")) != before_summary:
        _RUNTIME_STATS["archive_summary_applied"] += 1
    if reviewed.get("topic_trigger") and base._clean(out.get("topic")) != before_topic:
        _RUNTIME_STATS["archive_topic_applied"] += 1
    return out


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    reset_runtime_stats()
    base.load_review_copy_index = load_combined_review_copy_index
    base.humanize_state = safe_humanize_state
    _INSTALLED = True


def run_presentation_sync() -> dict[str, Any]:
    install()
    result = ux2.run_presentation_sync()
    result["run212_review_copy"] = dict(_RUNTIME_STATS)
    result["review_copy_policy"] = "current_authority_archive_copy_only"
    result["zero_gemini_calls"] = True
    return result


def run_body_sync() -> dict[str, Any]:
    result = ux2.run_body_sync()
    result["run212_review_copy"] = "presentation_only"
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python run212_member_review_copy.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
