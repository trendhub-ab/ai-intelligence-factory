#!/usr/bin/env python3
"""SQL-free contract guard for the secret-configured Notion Public mirror DB.

This guard uses only the Notion Public API. It makes ZERO Gemini/model requests and
never depends on Notion MCP query-data-sources SQL quota.
"""
from __future__ import annotations

import json
import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from typing import Any

import requests


NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "").strip()
NOTION_PUBLIC_DATABASE_ID = os.environ.get("NOTION_PUBLIC_DATABASE_ID", "").strip()
NOTION_PUBLIC_DATA_SOURCE_ID = os.environ.get("NOTION_PUBLIC_DATA_SOURCE_ID", "").strip()
NOTION_API_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11").strip() or "2026-03-11"
PROP_URL = "元情報URL"
MAX_RECORDS = 10000


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _schema_url() -> str:
    if NOTION_PUBLIC_DATA_SOURCE_ID:
        return f"https://api.notion.com/v1/data_sources/{NOTION_PUBLIC_DATA_SOURCE_ID}"
    return f"https://api.notion.com/v1/databases/{NOTION_PUBLIC_DATABASE_ID}"


def _query_url() -> str:
    if NOTION_PUBLIC_DATA_SOURCE_ID:
        return f"https://api.notion.com/v1/data_sources/{NOTION_PUBLIC_DATA_SOURCE_ID}/query"
    return f"https://api.notion.com/v1/databases/{NOTION_PUBLIC_DATABASE_ID}/query"


def canonicalize_url(value: str) -> str:
    """Canonical URL key compatible with the Public mirror's URL-based reconciliation."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        scheme = (parsed.scheme or "https").lower()
        host = (parsed.hostname or "").lower()
        if not host:
            return raw.rstrip("/")
        port = parsed.port
        netloc = host
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            netloc = f"{host}:{port}"
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")
        query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
        return urlunparse((scheme, netloc, path, "", query, ""))
    except Exception:
        return raw.rstrip("/")


def _plain_text(prop: dict[str, Any] | None) -> str:
    prop = prop or {}
    prop_type = prop.get("type")
    values = prop.get(prop_type) if prop_type in {"title", "rich_text"} else None
    if not isinstance(values, list):
        values = prop.get("title") or prop.get("rich_text") or []
    return "".join(str(item.get("plain_text") or "") for item in values).strip()


def validate_schema(properties: dict[str, Any]) -> str:
    url_prop = properties.get(PROP_URL) or {}
    if url_prop.get("type") != "url":
        raise ValueError(f"Public mirror requires {PROP_URL} as url property")
    title_props = [name for name, prop in properties.items() if (prop or {}).get("type") == "title"]
    if len(title_props) != 1:
        raise ValueError(f"Public mirror must have exactly one title property; found={title_props}")
    return title_props[0]


def fetch_all_pages() -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        body: dict[str, Any] = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        response = requests.post(_query_url(), headers=_headers(), json=body, timeout=20)
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("results") or []
        pages.extend(batch)
        if len(pages) > MAX_RECORDS:
            raise ValueError(f"Public mirror exceeds audit safety limit {MAX_RECORDS}")
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
        if not cursor:
            raise ValueError("Public mirror pagination has_more without next_cursor")
    return pages


def validate_pages(pages: list[dict[str, Any]], title_property: str) -> dict[str, Any]:
    by_key: dict[str, list[str]] = {}
    blank_titles: list[str] = []
    manual_without_url = 0

    for page in pages:
        page_id = str(page.get("id") or "")
        props = page.get("properties") or {}
        raw_url = str((props.get(PROP_URL) or {}).get("url") or "").strip()
        if not raw_url:
            # Public sync intentionally preserves manually added rows that do not map to internal URLs.
            manual_without_url += 1
            continue
        key = canonicalize_url(raw_url)
        by_key.setdefault(key, []).append(page_id)
        if not _plain_text(props.get(title_property)):
            blank_titles.append(page_id)

    duplicates = {key: ids for key, ids in by_key.items() if key and len(ids) > 1}
    if duplicates or blank_titles:
        raise ValueError(
            "Public mirror contract failed: "
            + json.dumps(
                {"duplicate_urls": duplicates, "blank_titles": blank_titles},
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    return {
        "records": len(pages),
        "url_managed_records": sum(len(ids) for ids in by_key.values()),
        "manual_without_url": manual_without_url,
        "duplicate_urls": 0,
        "blank_titles": 0,
        "zero_gemini_calls": True,
        "mcp_sql_calls": 0,
    }


def run() -> dict[str, Any]:
    if not NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is required")
    if not (NOTION_PUBLIC_DATA_SOURCE_ID or NOTION_PUBLIC_DATABASE_ID):
        raise ValueError("NOTION_PUBLIC_DATA_SOURCE_ID or NOTION_PUBLIC_DATABASE_ID is required")

    schema_response = requests.get(_schema_url(), headers=_headers(), timeout=20)
    schema_response.raise_for_status()
    properties = schema_response.json().get("properties") or {}
    if not isinstance(properties, dict):
        raise ValueError("Public mirror schema response has no properties map")
    title_property = validate_schema(properties)
    return validate_pages(fetch_all_pages(), title_property)


def main() -> int:
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
