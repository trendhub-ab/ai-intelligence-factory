"""Run174 monthly digest integrity guard.

The legacy subscriber Artifact path paginates Notion but historically stopped at 500 rows and
returned a partial dataset.  Run174 keeps the existing created_time semantics and row mapping,
while making completeness a product invariant:

* read through the legacy 500-row cap up to the current Notion query ceiling;
* observe Notion's request_status on every page;
* refuse a partial/ambiguous digest instead of silently publishing it;
* restore every wrapped global/helper even when the underlying fetch raises.

This layer is zero-Gemini and does not alter article generation or quality gates.
"""
from __future__ import annotations

import os
from typing import Any

_INSTALLED_ATTR = "_run174_monthly_digest_integrity_installed"
_DEFAULT_COMPLETE_LIMIT = 10_000
_RESULT_LIMIT_REASON = "query_result_limit_reached"


def _complete_limit() -> int:
    raw = os.environ.get("MONTHLY_DIGEST_COMPLETE_MAX_ITEMS", str(_DEFAULT_COMPLETE_LIMIT))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = _DEFAULT_COMPLETE_LIMIT
    # The current Notion query API cannot prove completeness beyond 10,000 rows in one query.
    return max(100, min(_DEFAULT_COMPLETE_LIMIT, value))


def _request_status(body: dict) -> tuple[str, str]:
    status = body.get("request_status") if isinstance(body, dict) else None
    if not isinstance(status, dict):
        return "", ""
    return (
        str(status.get("type") or "").strip().lower(),
        str(status.get("incomplete_reason") or "").strip().lower(),
    )


def install(pipeline_module: Any) -> Any:
    """Install a synchronous completeness wrapper around the legacy monthly fetcher."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    for name in ("fetch_monthly_dataset", "_query_notion_db_with_retry"):
        if not callable(getattr(pipeline_module, name, None)):
            raise RuntimeError(f"Run174 requires pipeline hook: {name}")

    original_fetch = pipeline_module.fetch_monthly_dataset
    original_query = pipeline_module._query_notion_db_with_retry

    def fetch_monthly_dataset_complete(start_utc: str, end_utc: str):
        hard_limit = _complete_limit()
        previous_limit = getattr(pipeline_module, "MONTHLY_DIGEST_MAX_ITEMS", 500)
        state = {
            "responses": 0,
            "parse_error": False,
            "incomplete": False,
            "last_has_more": False,
            "last_status_type": "",
            "last_incomplete_reason": "",
        }

        def observed_query(*args, **kwargs):
            response = original_query(*args, **kwargs)
            if response is None:
                return None
            try:
                body = response.json()
            except Exception:
                state["parse_error"] = True
                return response

            state["responses"] += 1
            state["last_has_more"] = bool((body or {}).get("has_more"))
            status_type, incomplete_reason = _request_status(body or {})
            state["last_status_type"] = status_type
            state["last_incomplete_reason"] = incomplete_reason
            if status_type == "incomplete" or incomplete_reason == _RESULT_LIMIT_REASON:
                state["incomplete"] = True
            return response

        # The legacy fetcher is synchronous.  Temporarily replace only its query helper and
        # row cap, then restore both in finally so unrelated Notion paths retain their contract.
        try:
            pipeline_module._query_notion_db_with_retry = observed_query
            pipeline_module.MONTHLY_DIGEST_MAX_ITEMS = hard_limit
            rows = original_fetch(start_utc, end_utc)
        finally:
            pipeline_module._query_notion_db_with_retry = original_query
            pipeline_module.MONTHLY_DIGEST_MAX_ITEMS = previous_limit

        if rows is None:
            return None

        count = len(rows)
        reason = ""
        if state["parse_error"]:
            reason = "request_status_unreadable"
        elif state["incomplete"]:
            reason = state["last_incomplete_reason"] or state["last_status_type"] or "incomplete"
        elif count > hard_limit:
            reason = "local_limit_exceeded"
        elif state["last_has_more"] and count >= hard_limit:
            reason = "local_limit_reached_with_more_results"
        elif count == hard_limit and state["last_status_type"] != "complete":
            # Exactly 10,000 can mean either an exact result or a server-truncated >10k query.
            # Accept it only when the API explicitly proves completeness.
            reason = "exact_limit_without_complete_status"

        if reason:
            pipeline_module.logger.error(
                "[RUN174 MONTHLY DIGEST INCOMPLETE] items=%s limit=%s reason=%s; refusing partial digest",
                count, hard_limit, reason,
            )
            return None

        pipeline_module.logger.info(
            "[RUN174 MONTHLY DIGEST COMPLETE] items=%s limit=%s responses=%s",
            count, hard_limit, state["responses"],
        )
        return rows

    pipeline_module.fetch_monthly_dataset = fetch_monthly_dataset_complete
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
