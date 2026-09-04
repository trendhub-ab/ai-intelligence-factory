#!/usr/bin/env python3
"""Run225 zero-model reconciliation for Screening Stock freshness.

This command never deletes/archives Notion pages and never changes Screening /
Decision scores, article state, Evidence, or adoption decisions.  It only
materializes non-Fresh lifecycle values in the existing Content Intelligence DB
property ``更新状態``.  Blank ``更新状態`` is the canonical compact encoding of
Fresh, which avoids hundreds of unnecessary Notion writes for the normal case.

Usage:
  python stock_lifecycle_reconcile.py              # read-only plan
  python stock_lifecycle_reconcile.py --apply      # apply changed lifecycle only
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import requests

from run225_stock_lifecycle import FRESH, classify_lifecycle

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "").strip()
NOTION_DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID", "").strip()
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "").strip()
NOTION_API_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11").strip()
REQUEST_PACING_SECONDS = max(0.20, float(os.environ.get("STOCK_LIFECYCLE_NOTION_PACING_SECONDS", "0.34")))
MAX_RECORDS = max(100, min(10000, int(os.environ.get("STOCK_LIFECYCLE_MAX_RECORDS", "5000"))))

PROP_NAME = "記事名"
PROP_EVALUATION_STATUS = "評価状態"
PROP_SOURCE = "情報源"
PROP_PUBLISHED_AT = "公開日"
PROP_ANALYZED_AT = "分析日"
PROP_SOURCE_SUMMARY = "元情報要約"
PROP_LIFECYCLE = "更新状態"
EVALUATION_STOCKED = "Stocked"


def _headers() -> dict[str, str]:
    if not NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is required")
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _query_url() -> str:
    if NOTION_DATA_SOURCE_ID:
        return f"https://api.notion.com/v1/data_sources/{NOTION_DATA_SOURCE_ID}/query"
    if NOTION_DATABASE_ID:
        return f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    raise ValueError("NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID is required")


def _plain(items: list[dict] | None) -> str:
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (items or [])
    ).strip()


def _title(prop: dict | None) -> str:
    return _plain((prop or {}).get("title") or [])


def _rich(prop: dict | None) -> str:
    return _plain((prop or {}).get("rich_text") or [])


def _select(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _date(prop: dict | None) -> str | None:
    value = ((prop or {}).get("date") or {}).get("start")
    return str(value).strip() if value else None


def _request(method: str, url: str, *, payload: dict | None = None, timeout: int = 25) -> requests.Response:
    last: requests.Response | None = None
    for attempt in range(6):
        last = requests.request(
            method,
            url,
            headers=_headers(),
            json=payload,
            timeout=timeout,
        )
        if last.status_code == 429 and attempt < 5:
            try:
                delay = float(last.headers.get("Retry-After") or 1.0)
            except (TypeError, ValueError):
                delay = 1.0
            time.sleep(max(0.5, min(delay, 30.0)))
            continue
        if 500 <= last.status_code < 600 and attempt < 5:
            time.sleep(min(1.0 * (attempt + 1), 6.0))
            continue
        return last
    assert last is not None
    return last


def query_stocked_pages() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = ""
    while True:
        payload: dict[str, Any] = {
            "page_size": 100,
            "filter": {
                "property": PROP_EVALUATION_STATUS,
                "select": {"equals": EVALUATION_STOCKED},
            },
        }
        if cursor:
            payload["start_cursor"] = cursor
        res = _request("POST", _query_url(), payload=payload)
        if res.status_code != 200:
            raise RuntimeError(f"Stock lifecycle query failed: HTTP {res.status_code} {res.text[:800]}")
        data = res.json()
        rows.extend(data.get("results") or [])
        if len(rows) > MAX_RECORDS:
            raise RuntimeError(f"Stock lifecycle query exceeded safety bound: {MAX_RECORDS}")
        if not data.get("has_more"):
            return rows
        cursor = str(data.get("next_cursor") or "")
        if not cursor:
            raise RuntimeError("Stock lifecycle pagination inconsistent: has_more without cursor")


def page_lifecycle(page: dict[str, Any], *, now: datetime | None = None):
    props = page.get("properties") or {}
    return classify_lifecycle(
        source=_select(props.get(PROP_SOURCE)),
        published_at=_date(props.get(PROP_PUBLISHED_AT)),
        analyzed_at=_date(props.get(PROP_ANALYZED_AT)),
        name=_title(props.get(PROP_NAME)),
        summary=_rich(props.get(PROP_SOURCE_SUMMARY)),
        now=now,
    )


def desired_materialized_value(label: str) -> str:
    # Fresh is by far the common state.  Blank=Fresh avoids a one-time rewrite of
    # the whole Stock warehouse and keeps later runs incremental.
    return "" if label == FRESH else label


def current_materialized_value(page: dict[str, Any]) -> str:
    return _select((page.get("properties") or {}).get(PROP_LIFECYCLE))


def _patch_lifecycle(page_id: str, materialized: str) -> None:
    payload = {
        "properties": {
            PROP_LIFECYCLE: {
                "select": {"name": materialized} if materialized else None,
            }
        }
    }
    res = _request("PATCH", f"https://api.notion.com/v1/pages/{page_id}", payload=payload)
    if res.status_code != 200:
        raise RuntimeError(
            f"Stock lifecycle update failed page={page_id}: HTTP {res.status_code} {res.text[:800]}"
        )
    time.sleep(REQUEST_PACING_SECONDS)


def reconcile(*, apply: bool = False, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    pages = query_stocked_pages()
    counts: Counter[str] = Counter()
    changes: list[dict[str, Any]] = []
    for page in pages:
        decision = page_lifecycle(page, now=now)
        counts[decision.label] += 1
        current = current_materialized_value(page)
        desired = desired_materialized_value(decision.label)
        if current == desired:
            continue
        props = page.get("properties") or {}
        changes.append(
            {
                "page_id": str(page.get("id") or ""),
                "name": _title(props.get(PROP_NAME)),
                "from": current or FRESH,
                "to": decision.label,
                "age_days": decision.age_days,
                "reason": decision.reason,
                "materialized": desired,
            }
        )

    updated = 0
    if apply:
        for change in changes:
            page_id = change["page_id"]
            if not page_id:
                raise RuntimeError("Stock lifecycle change is missing page id")
            _patch_lifecycle(page_id, change["materialized"])
            updated += 1

    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "destructive_deletes": 0,
        "apply": apply,
        "stocked_records": len(pages),
        "lifecycle_counts": dict(sorted(counts.items())),
        "changes_needed": len(changes),
        "updated": updated,
        "fresh_is_implicit_blank": True,
        "sample_changes": changes[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply lifecycle property changes")
    args = parser.parse_args()
    print(json.dumps(reconcile(apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
