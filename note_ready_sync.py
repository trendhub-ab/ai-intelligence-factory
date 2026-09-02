#!/usr/bin/env python3
"""Synchronize note-publishable Ready articles into a dedicated Notion DB.

Design:
- ZERO Gemini/model requests.
- Content Intelligence DB remains the quality Source of Truth.
- `記事状態=Ready` is necessary but no longer sufficient for publication: the source page
  must also contain a Ready manuscript stamped with the current publication contract.
- Historical/unversioned Ready inventory is excluded from the posting DB and any existing
  non-published destination row is revoked on the next sync.
- Human workflow fields (投稿状態, note公開URL, 投稿予定日, 投稿日) are never
  overwritten during normal Ready updates.
- If Ready/current-contract eligibility is later revoked, 品質状態 becomes Ready取消.
  Non-published rows are moved to 取下げ; already-published rows remain 投稿済み for
  auditability.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

import publication_contract as publication_contract

NOTION_API_KEY = (
    os.environ.get("NOTION_NOTE_READY_API_KEY", "").strip()
    or os.environ.get("NOTION_API_KEY", "").strip()
    or os.environ.get("NOTION_DECISION_INTELLIGENCE_API_KEY", "").strip()
)
NOTION_API_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11").strip()
SOURCE_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "").strip()
SOURCE_DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID", "").strip()
DEST_DATABASE_ID = os.environ.get("NOTION_NOTE_READY_DATABASE_ID", "").strip()
DEST_DATA_SOURCE_ID = os.environ.get("NOTION_NOTE_READY_DATA_SOURCE_ID", "").strip()

SOURCE_ARTICLE_STATUS = "記事状態"
SOURCE_READY = "Ready"

DEST_SCHEMA = {
    "記事タイトル": "title",
    "投稿状態": "select",
    "品質状態": "select",
    "判断": "select",
    "判断スコア": "number",
    "記事価値": "number",
    "情報源": "select",
    "元情報URL": "url",
    "一次情報URL": "url",
    "Content Intelligence": "url",
    "note公開URL": "url",
    "投稿予定日": "date",
    "投稿日": "date",
    "同期ID": "rich_text",
    "最終同期日": "date",
}
ALLOWED_SOURCES = {"GitHub", "HackerNews", "ArXiv", "ProductHunt"}
ALLOWED_DECISIONS = {"NOW", "TRY", "WATCH", "WAIT", "AVOID"}


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _query_url(data_source_id: str, database_id: str) -> str:
    if data_source_id:
        return f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    return f"https://api.notion.com/v1/databases/{database_id}/query"


def _schema_url(data_source_id: str, database_id: str) -> str:
    if data_source_id:
        return f"https://api.notion.com/v1/data_sources/{data_source_id}"
    return f"https://api.notion.com/v1/databases/{database_id}"


def _parent(data_source_id: str, database_id: str) -> dict[str, str]:
    return {"data_source_id": data_source_id} if data_source_id else {"database_id": database_id}


def _request(method: str, url: str, *, json: dict | None = None) -> requests.Response:
    last: requests.Response | None = None
    for attempt in range(5):
        last = requests.request(method, url, headers=_headers(), json=json, timeout=25)
        if last.status_code == 429:
            time.sleep(max(0.8, float(last.headers.get("Retry-After") or 1)))
            continue
        if 500 <= last.status_code < 600 and attempt < 4:
            time.sleep(1 + attempt)
            continue
        return last
    assert last is not None
    return last


def _query_db(data_source_id: str, database_id: str, *, payload: dict | None = None) -> list[dict]:
    body = dict(payload or {})
    body.setdefault("page_size", 100)
    rows: list[dict] = []
    while True:
        res = _request("POST", _query_url(data_source_id, database_id), json=body)
        if res.status_code != 200:
            raise RuntimeError(f"Notion query failed: HTTP {res.status_code} {res.text[:500]}")
        data = res.json()
        rows.extend(data.get("results") or [])
        if not data.get("has_more"):
            return rows
        cursor = data.get("next_cursor")
        if not cursor:
            return rows
        body["start_cursor"] = cursor


def _plain_text(values: list[dict] | None) -> str:
    return "".join(
        str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "")
        for x in (values or [])
    ).strip()


def _text(prop: dict | None) -> str:
    prop = prop or {}
    if prop.get("title") is not None:
        return _plain_text(prop.get("title"))
    if prop.get("rich_text") is not None:
        return _plain_text(prop.get("rich_text"))
    formula = prop.get("formula") or {}
    if isinstance(formula.get("string"), str):
        return formula["string"].strip()
    return ""


def _select(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _number(prop: dict | None) -> int | float | None:
    value = (prop or {}).get("number")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _url(prop: dict | None) -> str:
    return str((prop or {}).get("url") or "").strip()


def _first_url(text: str) -> str:
    for token in re.split(r"[\s<>,]+", str(text or "")):
        token = token.strip()
        if token.startswith(("https://", "http://")):
            return token
    return ""


def _normalize_page_id(value: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", str(value or "")).lower()


def _source_state(page: dict) -> dict[str, Any] | None:
    p = page.get("properties") or {}
    if _select(p.get(SOURCE_ARTICLE_STATUS)) != SOURCE_READY:
        return None
    sync_id = _normalize_page_id(page.get("id") or "")
    if not sync_id:
        return None
    title = _text(p.get("note記事タイトル")) or _text(p.get("記事名"))
    if not title:
        return None
    original_url = _url(p.get("元情報URL"))
    primary_url = _first_url(_text(p.get("一次情報URL"))) or original_url
    source = _select(p.get("情報源"))
    decision = _select(p.get("判断"))
    return {
        "sync_id": sync_id,
        "title": title,
        "decision": decision if decision in ALLOWED_DECISIONS else "",
        "decision_score": _number(p.get("判断スコア")),
        "article_value": _number(p.get("記事価値")),
        "source": source if source in ALLOWED_SOURCES else "",
        "original_url": original_url,
        "primary_url": primary_url,
        "content_page_url": str(page.get("url") or "").strip(),
    }


def _block_children(block_id: str) -> list[dict]:
    """Read root children used to persist the canonical manuscript code block."""
    rows: list[dict] = []
    cursor = ""
    for _ in range(30):
        query: dict[str, Any] = {"page_size": 100}
        if cursor:
            query["start_cursor"] = cursor
        res = _request(
            "GET",
            f"https://api.notion.com/v1/blocks/{block_id}/children?{urlencode(query)}",
        )
        if res.status_code != 200:
            raise RuntimeError(
                f"Content Intelligence manuscript fetch failed {block_id}: HTTP {res.status_code} {res.text[:300]}"
            )
        data = res.json()
        rows.extend(data.get("results") or [])
        if not data.get("has_more"):
            return rows
        cursor = str(data.get("next_cursor") or "")
        if not cursor:
            return rows
    raise RuntimeError("Content Intelligence manuscript pagination exceeded safety limit")


def _code_caption(block: dict) -> str:
    if block.get("type") != "code":
        return ""
    code = block.get("code") or {}
    return _plain_text(code.get("caption"))


def _source_has_current_ready_manuscript(page_id: str) -> bool:
    """Ready status is publishable only when current production provenance is present."""
    return any(
        publication_contract.is_current_ready_caption(_code_caption(block))
        for block in _block_children(page_id)
    )


def _destination_state(page: dict) -> dict[str, Any]:
    p = page.get("properties") or {}
    return {
        "page_id": str(page.get("id") or ""),
        "sync_id": _text(p.get("同期ID")),
        "posting_status": _select(p.get("投稿状態")),
        "quality_status": _select(p.get("品質状態")),
    }


def _rt(value: str) -> dict:
    value = str(value or "").strip()[:2000]
    if not value:
        return {"rich_text": []}
    return {"rich_text": [{"type": "text", "text": {"content": value}}]}


def _title(value: str) -> dict:
    value = str(value or "").strip()[:2000] or "タイトル未設定"
    return {"title": [{"type": "text", "text": {"content": value}}]}


def _sel(value: str) -> dict:
    return {"select": {"name": value}} if value else {"select": None}


def _system_props(state: dict[str, Any], *, today: str | None = None) -> dict[str, dict]:
    today = today or datetime.now(timezone.utc).date().isoformat()
    return {
        "記事タイトル": _title(state.get("title") or ""),
        "品質状態": _sel("Ready"),
        "判断": _sel(state.get("decision") or ""),
        "判断スコア": {"number": state.get("decision_score")},
        "記事価値": {"number": state.get("article_value")},
        "情報源": _sel(state.get("source") or ""),
        "元情報URL": {"url": state.get("original_url") or None},
        "一次情報URL": {"url": state.get("primary_url") or None},
        "Content Intelligence": {"url": state.get("content_page_url") or None},
        "同期ID": _rt(state.get("sync_id") or ""),
        "最終同期日": {"date": {"start": today}},
    }


def _validate_destination_schema() -> None:
    res = _request("GET", _schema_url(DEST_DATA_SOURCE_ID, DEST_DATABASE_ID))
    if res.status_code != 200:
        raise RuntimeError(
            f"note Ready destination schema fetch failed: HTTP {res.status_code} {res.text[:500]}"
        )
    props = res.json().get("properties") or {}
    missing = [name for name in DEST_SCHEMA if name not in props]
    wrong = [
        f"{name}:{(props.get(name) or {}).get('type')}!={expected}"
        for name, expected in DEST_SCHEMA.items()
        if name in props and (props.get(name) or {}).get("type") != expected
    ]
    quality_options = {
        x.get("name")
        for x in (((props.get("品質状態") or {}).get("select") or {}).get("options") or [])
    }
    posting_options = {
        x.get("name")
        for x in (((props.get("投稿状態") or {}).get("select") or {}).get("options") or [])
    }
    if not {"Ready", "Ready取消"} <= quality_options:
        wrong.append("品質状態:missing Ready/Ready取消")
    if not {"投稿待ち", "投稿準備中", "投稿済み", "保留", "取下げ"} <= posting_options:
        wrong.append("投稿状態:required options missing")
    if missing or wrong:
        raise ValueError(f"note Ready DB schema incompatible: missing={missing} wrong={wrong}")


def sync_note_ready_db() -> dict[str, Any]:
    if not NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY (or NOTION_NOTE_READY_API_KEY) is required")
    if not (SOURCE_DATA_SOURCE_ID or SOURCE_DATABASE_ID):
        raise ValueError("Content Intelligence source DB is not configured")
    if not (DEST_DATA_SOURCE_ID or DEST_DATABASE_ID):
        raise ValueError("note Ready destination DB is not configured")

    _validate_destination_schema()
    source_pages = _query_db(
        SOURCE_DATA_SOURCE_ID,
        SOURCE_DATABASE_ID,
        payload={
            "filter": {
                "property": SOURCE_ARTICLE_STATUS,
                "select": {"equals": SOURCE_READY},
            }
        },
    )

    states: list[dict[str, Any]] = []
    stale_contract = 0
    for page in source_pages:
        state = _source_state(page)
        if state is None:
            continue
        if not _source_has_current_ready_manuscript(state["sync_id"]):
            stale_contract += 1
            continue
        state["publication_contract"] = publication_contract.CONTRACT_ID
        states.append(state)
    source_by_id = {s["sync_id"]: s for s in states}

    dest_pages = _query_db(DEST_DATA_SOURCE_ID, DEST_DATABASE_ID)
    dest_by_id: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for page in dest_pages:
        current = _destination_state(page)
        sid = current["sync_id"]
        if not sid:
            continue
        if sid in dest_by_id:
            duplicates.add(sid)
        else:
            dest_by_id[sid] = current
    if duplicates:
        raise ValueError(f"Duplicate 同期ID in note Ready DB: {sorted(duplicates)[:10]}")

    created = updated = revoked = 0
    today = datetime.now(timezone.utc).date().isoformat()

    for sid, state in source_by_id.items():
        current = dest_by_id.get(sid)
        props = _system_props(state, today=today)
        if current is None:
            props["投稿状態"] = _sel("投稿待ち")
            res = _request(
                "POST",
                "https://api.notion.com/v1/pages",
                json={
                    "parent": _parent(DEST_DATA_SOURCE_ID, DEST_DATABASE_ID),
                    "properties": props,
                    "icon": {"type": "emoji", "emoji": "📝"},
                },
            )
            if res.status_code != 200:
                raise RuntimeError(f"note Ready create failed {sid}: {res.status_code} {res.text[:500]}")
            created += 1
        else:
            # Normal sync intentionally leaves human workflow fields untouched.
            res = _request(
                "PATCH",
                f"https://api.notion.com/v1/pages/{current['page_id']}",
                json={"properties": props},
            )
            if res.status_code != 200:
                raise RuntimeError(f"note Ready update failed {sid}: {res.status_code} {res.text[:500]}")
            updated += 1
        time.sleep(0.34)

    for sid, current in dest_by_id.items():
        if sid in source_by_id or current.get("quality_status") == "Ready取消":
            continue
        props: dict[str, dict] = {
            "品質状態": _sel("Ready取消"),
            "最終同期日": {"date": {"start": today}},
        }
        if current.get("posting_status") != "投稿済み":
            props["投稿状態"] = _sel("取下げ")
        res = _request(
            "PATCH",
            f"https://api.notion.com/v1/pages/{current['page_id']}",
            json={"properties": props},
        )
        if res.status_code != 200:
            raise RuntimeError(f"note Ready revoke failed {sid}: {res.status_code} {res.text[:500]}")
        revoked += 1
        time.sleep(0.34)

    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "publication_contract": publication_contract.CONTRACT_ID,
        "source_ready_status_rows": len(source_pages),
        "source_ready": len(source_by_id),
        "stale_publication_contract": stale_contract,
        "destination_rows": len(dest_pages),
        "created": created,
        "updated": updated,
        "revoked": revoked,
        "destination_data_source_id": DEST_DATA_SOURCE_ID,
    }


def main() -> None:
    print(sync_note_ready_db())


if __name__ == "__main__":
    main()
