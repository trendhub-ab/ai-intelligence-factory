"""Bounded validation lane for existing non-Ready Deep Dive candidates.

This module exists to keep article validation semantically separate from fresh
acquisition.  A candidate that is already stored in Notion must not need to pass
through acquisition/dedup again just because a publication gate changed.

Safety contract:
- read existing Deep Dive candidates only;
- exclude Ready and Pending Retry (the latter has its own recovery lane);
- prioritize Needs Editorial Review, then Quality Failed;
- never persist validation results to Notion/GitHub publication state;
- cap the Deep Dive request budget for this validation process.
"""
from __future__ import annotations

import os
from typing import Any


DEFAULT_LIMIT = 1
DEFAULT_SCAN_LIMIT = 100
DEFAULT_REQUEST_BUDGET = 4


def _select_name(prop: dict[str, Any] | None) -> str:
    selected = ((prop or {}).get("select") or {})
    return str(selected.get("name") or "")


def _read_current_statuses(pipeline, page_id: str) -> tuple[str, str] | None:
    """Read current lifecycle state without changing the page."""
    try:
        response = pipeline.requests.get(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=pipeline._notion_headers(),
            timeout=10,
        )
    except Exception as exc:
        pipeline.logger.warning("[ARTICLE REVALIDATION STATUS READ FAILED] %s: %s", page_id, exc)
        return None
    if int(getattr(response, "status_code", 0) or 0) != 200:
        pipeline.logger.warning(
            "[ARTICLE REVALIDATION STATUS READ FAILED] %s HTTP %s",
            page_id,
            getattr(response, "status_code", 0),
        )
        return None
    props = (response.json() or {}).get("properties", {})
    return (
        _select_name(props.get(pipeline.PROP_ARTICLE_STATUS)),
        _select_name(props.get(pipeline.PROP_CONTENT_STATUS)),
    )


def select_revalidation_items(pipeline, limit: int = DEFAULT_LIMIT, scan_limit: int = DEFAULT_SCAN_LIMIT):
    """Return existing non-Ready Deep Dive rows, independent of acquisition dedup.

    ``get_regen_test_items`` already reconstructs the source/candidate payload from
    Notion without screening or Stock writes.  We deliberately scan a larger bounded
    window, then verify the *current* page lifecycle before selecting anything.
    """
    limit = max(0, int(limit))
    if limit == 0:
        return []
    scan_limit = max(limit, min(100, int(scan_limit)))
    rows = pipeline.get_regen_test_items(scan_limit, "")
    if rows is None:
        return None

    editorial: list[dict] = []
    quality_failed: list[dict] = []
    for item in rows:
        page_id = str(item.get("notion_page_id") or "")
        if not page_id:
            continue
        statuses = _read_current_statuses(pipeline, page_id)
        if statuses is None:
            continue
        article_status, content_status = statuses

        # Ready is terminal for this lane. Pending Retry belongs to its dedicated
        # operational recovery lane and must never be double-consumed here.
        if article_status == pipeline.ARTICLE_STATUS_READY:
            continue
        if content_status == pipeline.CONTENT_STATUS_PENDING_RETRY:
            continue

        selected = dict(item)
        selected["revalidation_article_status"] = article_status
        selected["revalidation_content_status"] = content_status
        if article_status == pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW:
            editorial.append(selected)
        elif content_status == pipeline.CONTENT_STATUS_QUALITY_FAILED:
            quality_failed.append(selected)

    return (editorial + quality_failed)[:limit]


def _cap_validation_budget(pipeline) -> int:
    requested = max(1, int(os.environ.get("ARTICLE_REVALIDATION_REQUEST_BUDGET", str(DEFAULT_REQUEST_BUDGET))))
    budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    if budget is None:
        return requested
    current = max(0, int(getattr(budget, "budget", requested)))
    capped = min(current, requested)
    budget.budget = capped
    return capped


def run_article_revalidation(pipeline, limit: int | None = None) -> dict[str, Any]:
    """Regenerate current non-Ready candidates under today's gates, read-only.

    This intentionally calls the same production generation/gate path with
    ``persist_results=False``.  It produces private regen artifacts but cannot upgrade,
    downgrade, or duplicate a Notion row.  A later full run remains the only business
    write path.
    """
    selected_limit = max(1, int(limit or os.environ.get("ARTICLE_REVALIDATION_LIMIT", str(DEFAULT_LIMIT))))
    request_budget = _cap_validation_budget(pipeline)
    pipeline.logger.warning(
        "[ARTICLE REVALIDATION] existing non-Ready lane limit=%s request_budget=%s persist=false",
        selected_limit,
        request_budget,
    )
    items = select_revalidation_items(pipeline, selected_limit, DEFAULT_SCAN_LIMIT)
    if items is None:
        raise RuntimeError("Article revalidation candidate read failed")
    if not items:
        pipeline.logger.info("[ARTICLE REVALIDATION] no eligible existing non-Ready Deep Dive candidate")
        return {"selected": 0, "generated": 0, "accepted": 0, "rejected": 0}

    result = {"selected": len(items), "generated": 0, "accepted": 0, "rejected": 0}
    for index, item in enumerate(items, start=1):
        repo = item.get("repo") or {}
        name = repo.get("nameWithOwner") or "unknown"
        pipeline.logger.info(
            "[ARTICLE REVALIDATION %s/%s] %s prior_article=%s prior_content=%s",
            index,
            len(items),
            name,
            item.get("revalidation_article_status"),
            item.get("revalidation_content_status"),
        )
        is_safe, license_status = pipeline.legal_safety_gate(repo)
        if not is_safe:
            pipeline.logger.warning("[ARTICLE REVALIDATION SKIP: LICENSE] %s -> %s", name, license_status)
            continue
        try:
            generated = pipeline.generate_intelligence_report(
                repo,
                notion_page_id=item.get("notion_page_id"),
                screening_score=item.get("screening_score"),
                screening_reason=item.get("screening_reason", ""),
                candidate_rank=index,
                candidate_origin="article_revalidation",
                persist_results=False,
            )
        except pipeline.DailyQuotaExhaustedError:
            pipeline.logger.error("[ARTICLE REVALIDATION STOP] Gemini daily quota exhausted")
            break
        if not generated:
            continue
        manuscript, status = generated if isinstance(generated, tuple) else (generated, "accepted")
        result["generated"] += 1
        if status == "accepted":
            result["accepted"] += 1
        else:
            result["rejected"] += 1
        pipeline.logger.info(
            "[ARTICLE REVALIDATION RESULT] %s status=%s chars=%s",
            name,
            status,
            len(manuscript or ""),
        )

    pipeline.logger.info("[ARTICLE REVALIDATION COMPLETE] %s", result)
    return result
