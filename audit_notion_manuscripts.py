#!/usr/bin/env python3
"""Read-only Content Intelligence manuscript inventory.

This script is intentionally incapable of mutating Notion. It only:
- POSTs a data-source query (read operation), and
- GETs direct block children.

It never prints manuscript bodies. The report contains metadata needed to
identify pages with multiple manuscript blocks and to prove a unique canonical
candidate from the current note article title when possible.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11")
READY_CAPTION_PREFIX = "AIIF_MANUSCRIPT:READY"
REVIEW_CAPTION = "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"


def _headers() -> dict[str, str]:
    token = os.environ.get("NOTION_API_KEY", "").strip()
    if not token:
        raise RuntimeError("NOTION_API_KEY is required")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _read_json(method: str, url: str, payload: dict | None = None) -> dict:
    # This is a read-only audit. Notion's data-source query uses POST by API design.
    if method not in {"GET", "POST"}:
        raise RuntimeError(f"write method forbidden in audit: {method}")
    if method == "POST" and "/data_sources/" not in url:
        raise RuntimeError(f"POST forbidden outside data-source query: {url}")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429 or 500 <= exc.code < 600:
                time.sleep(min(2 ** attempt, 8))
                continue
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Notion HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"Notion request failed after retries: {last_error}")


def _plain(values: list[dict] | None) -> str:
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (values or [])
    ).strip()


def _prop_text(prop: dict | None) -> str:
    prop = prop or {}
    if prop.get("title") is not None:
        return _plain(prop.get("title"))
    if prop.get("rich_text") is not None:
        return _plain(prop.get("rich_text"))
    return ""


def _prop_select(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _query_all(data_source_id: str) -> list[dict]:
    rows: list[dict] = []
    cursor = ""
    while True:
        payload: dict = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        data = _read_json("POST", f"{API_BASE}/data_sources/{data_source_id}/query", payload)
        rows.extend(data.get("results") or [])
        if not data.get("has_more"):
            return rows
        cursor = str(data.get("next_cursor") or "")
        if not cursor:
            raise RuntimeError("Notion data-source pagination missing next_cursor")


def _children(page_id: str) -> list[dict]:
    rows: list[dict] = []
    cursor = ""
    for _ in range(50):
        query = {"page_size": "100"}
        if cursor:
            query["start_cursor"] = cursor
        url = f"{API_BASE}/blocks/{page_id}/children?{urllib.parse.urlencode(query)}"
        # Notion documents an average request-rate limit; keep this exhaustive
        # audit deliberately below it instead of bursting until 429.
        time.sleep(0.38)
        data = _read_json("GET", url)
        rows.extend(data.get("results") or [])
        if not data.get("has_more"):
            return rows
        cursor = str(data.get("next_cursor") or "")
        if not cursor:
            raise RuntimeError(f"block pagination missing next_cursor for {page_id}")
    raise RuntimeError(f"block pagination exceeded safety limit for {page_id}")


def _code_body(block: dict) -> str:
    if block.get("type") != "code":
        return ""
    code = block.get("code") or {}
    if str(code.get("language") or "").lower() != "markdown":
        return ""
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (code.get("rich_text") or [])
    )


def _code_caption(block: dict) -> str:
    if block.get("type") != "code":
        return ""
    return _plain(((block.get("code") or {}).get("caption")))


def _h1(body: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", body or "")
    return match.group(1).strip() if match else ""


def _sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _caption_kind(caption: str) -> str:
    if caption == REVIEW_CAPTION:
        return "review"
    if caption.startswith(READY_CAPTION_PREFIX):
        return "ready"
    if not caption:
        return "captionless"
    return "other"


def audit() -> dict:
    data_source_id = os.environ.get("NOTION_DATA_SOURCE_ID", "").strip()
    if not data_source_id:
        raise RuntimeError("NOTION_DATA_SOURCE_ID is required")
    rows = _query_all(data_source_id)
    findings: list[dict] = []
    scanned = 0
    manuscript_pages = 0
    multiple_pages = 0
    ambiguous_multiple = 0
    unique_title_match_multiple = 0

    for page in rows:
        page_id = str(page.get("id") or "")
        if not page_id:
            continue
        scanned += 1
        props = page.get("properties") or {}
        expected_title = _prop_text(props.get("note記事タイトル"))
        article_name = _prop_text(props.get("記事名"))
        article_status = _prop_select(props.get("記事状態"))
        blocks = []
        for block in _children(page_id):
            body = _code_body(block)
            if not body:
                continue
            caption = _code_caption(block)
            blocks.append({
                "block_id": str(block.get("id") or ""),
                "caption_kind": _caption_kind(caption),
                "h1": _h1(body),
                "body_sha16": _sha(body),
            })
        if not blocks:
            continue
        manuscript_pages += 1
        title_matches = [b for b in blocks if expected_title and b["h1"] == expected_title]
        if len(blocks) > 1:
            multiple_pages += 1
            if len(title_matches) == 1:
                unique_title_match_multiple += 1
                canonical_block_id = title_matches[0]["block_id"]
                classification = "unique_current_title_match"
            else:
                ambiguous_multiple += 1
                canonical_block_id = ""
                classification = "ambiguous"
            findings.append({
                "page_id": page_id.replace("-", ""),
                "article_name": article_name,
                "article_status": article_status,
                "expected_title": expected_title,
                "manuscript_count": len(blocks),
                "title_match_count": len(title_matches),
                "classification": classification,
                "canonical_block_id": canonical_block_id,
                "blocks": blocks,
            })

    return {
        "schema_version": 1,
        "read_only": True,
        "data_source_id": data_source_id,
        "rows_queried": len(rows),
        "pages_scanned": scanned,
        "pages_with_manuscript": manuscript_pages,
        "pages_with_multiple_manuscripts": multiple_pages,
        "multiple_with_unique_current_title_match": unique_title_match_multiple,
        "multiple_ambiguous": ambiguous_multiple,
        "findings": findings,
    }


def main() -> int:
    report = audit()
    out = Path(os.environ.get("AIIF_AUDIT_OUTPUT", "artifacts/notion_manuscript_audit.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: report[k] for k in (
        "rows_queried", "pages_scanned", "pages_with_manuscript",
        "pages_with_multiple_manuscripts", "multiple_with_unique_current_title_match",
        "multiple_ambiguous",
    )}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
