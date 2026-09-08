"""Run286: fail-closed Notion consistency precision for bounded Ready recovery.

This module is operational only. It does not alter article bytes, quality gates, evidence
requirements, model routing, or provider budgets.

The recovery selector may start from an eventually-consistent Notion database query. Before
any model call is allowed, Run286 can re-read the selected page directly and require that the
live Article Status is still Ready. A mismatch, failed read, or empty status returns no
candidate and therefore spends zero Gemini requests.
"""
from __future__ import annotations

from typing import Any, Callable


def filter_live_ready_items(
    pipeline: Any,
    items: list[dict[str, Any]] | None,
    status_reader: Callable[[str], str | None],
):
    """Return only selected rows whose direct page status is still Ready.

    This function performs no I/O itself; the caller supplies the existing direct page-status
    reader. It is therefore deterministic in tests and cannot introduce a provider/model call.
    """
    if items is None or not items:
        return items

    expected = str(getattr(pipeline, "ARTICLE_STATUS_READY", "Ready") or "Ready")
    confirmed: list[dict[str, Any]] = []
    for item in items:
        page_id = str((item or {}).get("notion_page_id") or "").strip()
        live_status = status_reader(page_id) if page_id else None
        if live_status != expected:
            logger = getattr(pipeline, "logger", None)
            if logger is not None:
                logger.info(
                    "[RUN286 RECOVERY LIVE STATUS SKIP] page_id=%s query_status=Ready live_status=%s",
                    page_id or "missing",
                    live_status or "UNAVAILABLE",
                )
            continue
        confirmed.append(item)
    return confirmed


def install_recovery_live_status_guard(recovery_module: Any) -> None:
    """Compatibility installer used by isolated tests and optional local harnesses."""
    if bool(getattr(recovery_module, "_run286_live_status_guard_installed", False)):
        return

    original = getattr(recovery_module, "select_stale_ready_items", None)
    if not callable(original):
        setattr(recovery_module, "_run286_live_status_guard_installed", True)
        return

    def guarded_select(pipeline, limit=1, scan_limit=100):
        items = original(pipeline, limit=limit, scan_limit=scan_limit)
        return filter_live_ready_items(
            pipeline,
            items,
            lambda page_id: recovery_module._read_article_status(pipeline, page_id),
        )

    recovery_module.select_stale_ready_items = guarded_select
    setattr(recovery_module, "_run286_live_status_guard_installed", True)
    setattr(recovery_module, "_run286_original_select_stale_ready_items", original)
