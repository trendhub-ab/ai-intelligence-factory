"""Run286: fail-closed Notion consistency precision for bounded Ready recovery.

This module is operational only. It does not alter article bytes, quality gates, evidence
requirements, model routing, or provider budgets.

The recovery selector may start from an eventually-consistent Notion database query. Before
any model call is allowed, Run286 re-reads the selected page directly and requires that the
live Article Status is still Ready. A mismatch, failed read, or empty status returns no
candidate and therefore spends zero Gemini requests.
"""
from __future__ import annotations

from typing import Any


def install_recovery_live_status_guard(recovery_module: Any) -> None:
    """Guard the selected stale-Ready candidate with a direct page status read.

    The historical selector remains authoritative for ranking, source allowlisting, license
    checks, and publication-contract staleness. Run286 only validates the final selected row
    immediately before the existing recovery controller can call the generator.
    """
    if bool(getattr(recovery_module, "_run286_live_status_guard_installed", False)):
        return

    original = getattr(recovery_module, "select_stale_ready_items", None)
    if not callable(original):
        setattr(recovery_module, "_run286_live_status_guard_installed", True)
        return

    def guarded_select(pipeline, limit=1, scan_limit=100):
        items = original(pipeline, limit=limit, scan_limit=scan_limit)
        if items is None or not items:
            return items

        confirmed = []
        for item in items:
            page_id = str((item or {}).get("notion_page_id") or "").strip()
            live_status = recovery_module._read_article_status(pipeline, page_id) if page_id else None
            expected = str(getattr(pipeline, "ARTICLE_STATUS_READY", "Ready") or "Ready")
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

    recovery_module.select_stale_ready_items = guarded_select
    setattr(recovery_module, "_run286_live_status_guard_installed", True)
    setattr(recovery_module, "_run286_original_select_stale_ready_items", original)
