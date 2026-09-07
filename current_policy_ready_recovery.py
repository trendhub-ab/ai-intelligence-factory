"""Bounded recovery for historical Ready rows invalidated by publication-policy changes.

Run282 deliberately separates inventory recovery from normal acquisition.  It reads existing
Deep Dive rows that are still marked Ready, proves that they do *not* contain a manuscript
valid under the checked-out Publication Contract, ranks them with already-persisted business
signals, and regenerates at most one row on its original Notion page.

Safety / cost contract:
- no fresh acquisition, screening, Product Review, or Stock creation;
- active public sources only (GitHub / HackerNews / ArXiv / OfficialVendor);
- historical ProductHunt / unknown sources are excluded fail-closed;
- at most one candidate and four deep-dive requests per explicit ONE-SHOT;
- accepted generation is not counted as recovered until Notion still says Ready *and* a
  byte-valid current-policy manuscript block can be read back from the same page;
- no status is ever forced to Ready by this controller; canonical gates/persistence own it.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import publication_contract
from publication_source_contract import ACTIVE_PUBLIC_SOURCES

HARD_MAX_RECOVERY_LIMIT = 1
HARD_MAX_REQUEST_BUDGET = 4
DEFAULT_SCAN_LIMIT = 100


def _select_name(prop: dict[str, Any] | None) -> str:
    return str((((prop or {}).get("select") or {}).get("name")) or "").strip()


def _number(prop: dict[str, Any] | None) -> float:
    value = (prop or {}).get("number")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _date_start(prop: dict[str, Any] | None) -> str:
    return str((((prop or {}).get("date") or {}).get("start")) or "").strip()


def _plain(values: list[dict] | None) -> str:
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (values or [])
    ).strip()


def _code_body(block: dict[str, Any]) -> str:
    if block.get("type") != "code":
        return ""
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (((block.get("code") or {}).get("rich_text")) or [])
    )


def _code_caption(block: dict[str, Any]) -> str:
    if block.get("type") != "code":
        return ""
    return _plain(((block.get("code") or {}).get("caption")) or [])


def _block_children(pipeline, page_id: str) -> list[dict] | None:
    rows: list[dict] = []
    cursor = ""
    for _ in range(30):
        query: dict[str, Any] = {"page_size": 100}
        if cursor:
            query["start_cursor"] = cursor
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?{urlencode(query)}"
        try:
            response = pipeline.requests.get(url, headers=pipeline._notion_headers(), timeout=15)
        except Exception as exc:
            pipeline.logger.warning("[CURRENT POLICY RECOVERY BLOCK READ FAILED] %s: %s", page_id, exc)
            return None
        if int(getattr(response, "status_code", 0) or 0) != 200:
            pipeline.logger.warning(
                "[CURRENT POLICY RECOVERY BLOCK READ FAILED] %s HTTP %s",
                page_id,
                getattr(response, "status_code", 0),
            )
            return None
        data = response.json() or {}
        rows.extend(data.get("results") or [])
        if not data.get("has_more"):
            return rows
        cursor = str(data.get("next_cursor") or "").strip()
        if not cursor:
            return rows
    pipeline.logger.warning("[CURRENT POLICY RECOVERY BLOCK READ FAILED] pagination safety limit: %s", page_id)
    return None


def _has_current_ready_manuscript(pipeline, page_id: str) -> bool | None:
    """Use the exact Publication Contract predicate used by Note Ready sync."""
    blocks = _block_children(pipeline, page_id)
    if blocks is None:
        return None
    for block in blocks:
        body = _code_body(block)
        if body and publication_contract.is_current_ready_block(body, _code_caption(block)):
            return True
    return False


def _read_article_status(pipeline, page_id: str) -> str | None:
    try:
        response = pipeline.requests.get(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=pipeline._notion_headers(),
            timeout=10,
        )
    except Exception as exc:
        pipeline.logger.warning("[CURRENT POLICY RECOVERY STATUS READ FAILED] %s: %s", page_id, exc)
        return None
    if int(getattr(response, "status_code", 0) or 0) != 200:
        pipeline.logger.warning(
            "[CURRENT POLICY RECOVERY STATUS READ FAILED] %s HTTP %s",
            page_id,
            getattr(response, "status_code", 0),
        )
        return None
    props = (response.json() or {}).get("properties") or {}
    return _select_name(props.get(pipeline.PROP_ARTICLE_STATUS))


def _reconstruct_item(pipeline, page: dict[str, Any]) -> dict[str, Any] | None:
    props = page.get("properties") or {}
    page_id = str(page.get("id") or "").strip()
    name = pipeline._notion_plain_text(props.get(pipeline.PROP_NAME, {}))
    url = str((props.get(pipeline.PROP_URL, {}) or {}).get("url") or "").strip()
    source = _select_name(props.get(pipeline.PROP_SOURCE))
    if not page_id or not name or not url or source not in set(ACTIVE_PUBLIC_SOURCES):
        return None

    license_text = pipeline._notion_plain_text(props.get(pipeline.PROP_LICENSE, {}))
    engagement = int(_number(props.get(pipeline.PROP_ENGAGEMENT)))
    published_at = _date_start(props.get(pipeline.PROP_PUBLISHED_AT))
    analyzed_at = _date_start(props.get(pipeline.PROP_ANALYZED_AT))
    screening_score = int(_number(props.get(pipeline.PROP_SCREENING_SCORE)))
    article_value = _number(props.get(pipeline.PROP_ARTICLE_VALUE))
    decision_score = _number(props.get(pipeline.PROP_SCORE))
    summary = pipeline._notion_plain_text(props.get(pipeline.PROP_SOURCE_SUMMARY, {}))
    screening_reason = pipeline._notion_plain_text(props.get(pipeline.PROP_SCREENING_REASON, {}))

    details: dict[str, Any] = {
        "regen_note": "Run282 current-policy Ready recovery from existing Notion Deep Dive",
    }
    if source in {"HackerNews", "OfficialVendor"}:
        details["external_url"] = url
        details["official_url"] = url

    item = {
        "notion_page_id": page_id,
        "screening_score": screening_score,
        "screening_reason": screening_reason or "Run282 current-policy Ready recovery",
        "article_value": article_value,
        "decision_score": decision_score,
        "analyzed_at": analyzed_at,
        "repo": {
            "nameWithOwner": name,
            "description": summary or "Existing Deep Dive current-policy recovery",
            "url": url,
            "stargazerCount": engagement,
            "source": source,
            "publishedAt": published_at or None,
            "sourceContext": "",
            "primaryUrl": url,
            "sourceDetails": details,
            "licenseInfo": ({"spdxId": license_text} if source == "GitHub" and license_text else None),
        },
    }
    return item


def _business_rank(item: dict[str, Any]) -> tuple[float, float, int, str, str]:
    """Persisted-value rank only: no model-estimated commercial score is invented here."""
    repo = item.get("repo") or {}
    return (
        float(item.get("article_value") or 0),
        float(item.get("decision_score") or 0),
        int(item.get("screening_score") or 0),
        str(item.get("analyzed_at") or ""),
        str(repo.get("nameWithOwner") or ""),
    )


def select_stale_ready_items(pipeline, limit: int = HARD_MAX_RECOVERY_LIMIT, scan_limit: int = DEFAULT_SCAN_LIMIT):
    """Select highest-value stale Ready rows without spending a Gemini request."""
    limit = max(0, min(HARD_MAX_RECOVERY_LIMIT, int(limit)))
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
    for page in (response.json() or {}).get("results", []):
        props = page.get("properties") or {}
        source = _select_name(props.get(pipeline.PROP_SOURCE))
        if source not in set(ACTIVE_PUBLIC_SOURCES):
            unsupported += 1
            continue
        item = _reconstruct_item(pipeline, page)
        if item is not None:
            candidates.append(item)
    candidates.sort(key=_business_rank, reverse=True)

    selected: list[dict[str, Any]] = []
    for item in candidates:
        repo = item.get("repo") or {}
        is_safe, license_status = pipeline.legal_safety_gate(repo)
        if not is_safe:
            pipeline.logger.info(
                "[CURRENT POLICY RECOVERY SKIP: LICENSE] %s -> %s",
                repo.get("nameWithOwner"), license_status,
            )
            continue
        current = _has_current_ready_manuscript(pipeline, str(item.get("notion_page_id") or ""))
        if current is None:
            # Read uncertainty is never interpreted as stale; fail closed for this row.
            continue
        if current:
            continue
        selected.append(item)
        if len(selected) >= limit:
            break

    pipeline.logger.info(
        "[CURRENT POLICY RECOVERY SELECT] ready_rows=%s supported=%s unsupported=%s selected=%s",
        len((response.json() or {}).get("results", [])),
        len(candidates),
        unsupported,
        len(selected),
    )
    return selected


def _cap_recovery_budget(pipeline) -> int:
    requested = max(
        1,
        int(os.environ.get("CURRENT_POLICY_READY_RECOVERY_REQUEST_BUDGET", str(HARD_MAX_REQUEST_BUDGET))),
    )
    requested = min(HARD_MAX_REQUEST_BUDGET, requested)
    deep_budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    if deep_budget is not None:
        current = max(0, int(getattr(deep_budget, "budget", requested)))
        deep_budget.budget = min(current, requested)
        return int(deep_budget.budget)
    return requested


def run_current_policy_ready_recovery(pipeline, limit: int | None = None) -> dict[str, Any]:
    """Persist exactly one high-value stale Ready candidate under today's policy."""
    requested_limit = int(limit or os.environ.get("CURRENT_POLICY_READY_RECOVERY_LIMIT", "1"))
    selected_limit = max(1, min(HARD_MAX_RECOVERY_LIMIT, requested_limit))
    request_budget = _cap_recovery_budget(pipeline)
    pipeline.logger.warning(
        "[CURRENT POLICY RECOVERY] limit=%s request_budget=%s persist=true fresh_acquisition=false",
        selected_limit,
        request_budget,
    )

    items = select_stale_ready_items(pipeline, selected_limit, DEFAULT_SCAN_LIMIT)
    if items is None:
        raise RuntimeError("Current-policy Ready recovery candidate read failed")
    if not items:
        return {"selected": 0, "generated": 0, "accepted": 0, "recovered": 0, "rejected": 0}

    result = {"selected": len(items), "generated": 0, "accepted": 0, "recovered": 0, "rejected": 0}
    for rank, item in enumerate(items, start=1):
        repo = item.get("repo") or {}
        name = str(repo.get("nameWithOwner") or "unknown")
        page_id = str(item.get("notion_page_id") or "")
        pipeline.logger.info(
            "[CURRENT POLICY RECOVERY %s/%s] %s article_value=%s decision_score=%s",
            rank,
            len(items),
            name,
            item.get("article_value"),
            item.get("decision_score"),
        )
        try:
            generated = pipeline.generate_intelligence_report(
                repo,
                notion_page_id=page_id,
                screening_score=item.get("screening_score"),
                screening_reason=item.get("screening_reason", ""),
                candidate_rank=rank,
                candidate_origin="current_policy_ready_recovery",
                attribution_context=item,
                persist_results=True,
            )
        except pipeline.DailyQuotaExhaustedError:
            pipeline.logger.error("[CURRENT POLICY RECOVERY STOP] Gemini daily quota exhausted")
            break
        if not generated:
            continue

        _manuscript, status = generated if isinstance(generated, tuple) else (generated, "accepted")
        result["generated"] += 1
        if status != "accepted":
            result["rejected"] += 1
            continue
        result["accepted"] += 1

        # Trust the persisted artifact, not the in-memory return value.  The candidate is
        # recovered only when the original page is still Ready and contains a current-policy
        # byte-valid manuscript after the write.
        article_status = _read_article_status(pipeline, page_id)
        current = _has_current_ready_manuscript(pipeline, page_id)
        if article_status == pipeline.ARTICLE_STATUS_READY and current is True:
            result["recovered"] += 1
            pipeline.logger.info("[CURRENT POLICY RECOVERY VERIFIED] %s", name)
        else:
            pipeline.logger.error(
                "[CURRENT POLICY RECOVERY VERIFY FAILED] %s article_status=%s current_block=%s",
                name,
                article_status,
                current,
            )

    pipeline.logger.info("[CURRENT POLICY RECOVERY COMPLETE] %s", result)
    return result
