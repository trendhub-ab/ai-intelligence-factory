"""Run368 bounded batch recovery for historical Ready rows.

This lane deliberately does not weaken Run282.  Run282 remains hard-capped at one row /
four model requests.  Run368 is a separate explicit manual lane for recovering a small batch
after source/evidence migration work has already made the rows eligible for an active public
source contract.

Safety contract:
- existing Deep Dive + Ready rows only; no acquisition, screening, Product Review or Stock creation;
- active public sources only;
- at most three candidates and twelve deep-dive/model requests per explicit invocation;
- each candidate is re-read from Notion after generation and counts as recovered only if it is
  still Ready and contains a byte-valid current Publication Contract manuscript;
- no status is forced to Ready here; canonical generation/Gates/persistence own the result;
- no note draft, browser/VM fan-out, or public publication.
"""
from __future__ import annotations

import os
from typing import Any

import current_policy_ready_recovery as single
from publication_source_contract import ACTIVE_PUBLIC_SOURCES
from run285_operational_accounting import increment_status_count, install_recovery_evidence_audit
from run286_notion_consistency_precision import filter_live_ready_items

HARD_MAX_BATCH_LIMIT = 3
HARD_MAX_BATCH_REQUEST_BUDGET = 12
DEFAULT_SCAN_LIMIT = 100


def select_stale_ready_items_batch(pipeline, limit: int = HARD_MAX_BATCH_LIMIT, scan_limit: int = DEFAULT_SCAN_LIMIT):
    """Select up to three highest-value supported stale Ready rows with zero model calls."""
    limit = max(0, min(HARD_MAX_BATCH_LIMIT, int(limit)))
    if limit == 0:
        return []
    if not str(getattr(pipeline, "NOTION_API_KEY", "") or "").strip():
        return []

    payload = {
        "filter": {"and": [
            {"property": pipeline.PROP_CONTENT_STATUS, "select": {"equals": pipeline.CONTENT_STATUS_DEEP_DIVE}},
            {"property": pipeline.PROP_ARTICLE_STATUS, "select": {"equals": pipeline.ARTICLE_STATUS_READY}},
        ]},
        "page_size": min(100, max(limit, int(scan_limit))),
    }
    response = pipeline._query_notion_db_with_retry(
        pipeline._notion_query_url(), pipeline._notion_headers(), payload
    )
    if response is None:
        return None

    candidates: list[dict[str, Any]] = []
    unsupported = 0
    active = set(ACTIVE_PUBLIC_SOURCES)
    rows = (response.json() or {}).get("results", [])
    for page in rows:
        props = page.get("properties") or {}
        source = single._select_name(props.get(pipeline.PROP_SOURCE))
        if source not in active:
            unsupported += 1
            continue
        item = single._reconstruct_item(pipeline, page)
        if item is not None:
            candidates.append(item)
    candidates.sort(key=single._business_rank, reverse=True)

    selected: list[dict[str, Any]] = []
    for item in candidates:
        repo = item.get("repo") or {}
        is_safe, license_status = pipeline.legal_safety_gate(repo)
        if not is_safe:
            pipeline.logger.info(
                "[RUN368 SKIP: LICENSE] %s -> %s", repo.get("nameWithOwner"), license_status
            )
            continue
        current = single._has_current_ready_manuscript(
            pipeline, str(item.get("notion_page_id") or "")
        )
        if current is None:
            continue
        if current:
            continue
        selected.append(item)
        if len(selected) >= limit:
            break

    pipeline.logger.info(
        "[RUN368 SELECT] ready_rows=%s supported=%s unsupported=%s selected=%s",
        len(rows), len(candidates), unsupported, len(selected),
    )
    return selected


def _cap_batch_budget(pipeline) -> int:
    requested = max(
        1,
        int(os.environ.get(
            "CURRENT_POLICY_READY_BATCH_REQUEST_BUDGET",
            str(HARD_MAX_BATCH_REQUEST_BUDGET),
        )),
    )
    requested = min(HARD_MAX_BATCH_REQUEST_BUDGET, requested)
    deep_budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    if deep_budget is not None:
        current = max(0, int(getattr(deep_budget, "budget", requested)))
        deep_budget.budget = min(current, requested)
        return int(deep_budget.budget)
    return requested


def _empty_result(selected: int = 0) -> dict[str, Any]:
    return {
        "selected": int(selected),
        "processed": 0,
        "generated": 0,
        "accepted": 0,
        "recovered": 0,
        "rejected": 0,
        "persisted_status_counts": {},
    }


def run_current_policy_ready_batch_recovery(pipeline, limit: int | None = None) -> dict[str, Any]:
    """Regenerate and verify at most three stale Ready rows under today's policy."""
    requested_limit = int(limit or os.environ.get("CURRENT_POLICY_READY_BATCH_LIMIT", "3"))
    selected_limit = max(1, min(HARD_MAX_BATCH_LIMIT, requested_limit))
    request_budget = _cap_batch_budget(pipeline)
    pipeline.logger.warning(
        "[RUN368 BATCH RECOVERY] limit=%s request_budget=%s persist=true fresh_acquisition=false",
        selected_limit, request_budget,
    )

    install_recovery_evidence_audit(pipeline)
    items = select_stale_ready_items_batch(pipeline, selected_limit, DEFAULT_SCAN_LIMIT)
    if str(os.environ.get("ENABLE_RUN286_NOTION_LIVE_STATUS_GUARD", "")).strip().lower() in {
        "1", "true", "yes", "on"
    }:
        items = filter_live_ready_items(
            pipeline,
            items,
            lambda page_id: single._read_article_status(pipeline, page_id),
        )
    if items is None:
        raise RuntimeError("Run368 Ready batch recovery candidate read failed")
    if not items:
        return _empty_result(0)

    result = _empty_result(len(items))
    for rank, item in enumerate(items, start=1):
        repo = item.get("repo") or {}
        name = str(repo.get("nameWithOwner") or "unknown")
        page_id = str(item.get("notion_page_id") or "")
        pipeline.logger.info(
            "[RUN368 %s/%s] %s article_value=%s decision_score=%s",
            rank, len(items), name, item.get("article_value"), item.get("decision_score"),
        )
        try:
            generated = pipeline.generate_intelligence_report(
                repo,
                notion_page_id=page_id,
                screening_score=item.get("screening_score"),
                screening_reason=item.get("screening_reason", ""),
                candidate_rank=rank,
                candidate_origin="current_policy_ready_batch_recovery",
                attribution_context=item,
                persist_results=True,
            )
        except pipeline.DailyQuotaExhaustedError:
            pipeline.logger.error("[RUN368 STOP] Gemini daily quota exhausted")
            break

        result["processed"] += 1
        article_status = single._read_article_status(pipeline, page_id)
        increment_status_count(result["persisted_status_counts"], article_status)
        if not generated:
            continue

        _manuscript, status = generated if isinstance(generated, tuple) else (generated, "accepted")
        result["generated"] += 1
        if status != "accepted":
            result["rejected"] += 1
            continue
        result["accepted"] += 1

        current = single._has_current_ready_manuscript(pipeline, page_id)
        if article_status == pipeline.ARTICLE_STATUS_READY and current is True:
            result["recovered"] += 1
            pipeline.logger.info("[RUN368 VERIFIED] %s", name)
        else:
            pipeline.logger.error(
                "[RUN368 VERIFY FAILED] %s article_status=%s current_block=%s",
                name, article_status, current,
            )

    pipeline.logger.info("[RUN368 COMPLETE] %s", result)
    return result
