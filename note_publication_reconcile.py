#!/usr/bin/env python3
"""Reconcile note's private-draft identity and human-published articles with Notion.

Publication stays human-only. Public reconciliation reads the creator's public note RSS feed and,
only when one exact Ready queue row has one exact public-title match, records the public URL/date.
The private-draft helper binds the already-verified note edit-route identity to the same queue row
before it can advance to 投稿準備中. Raw private draft URLs are never persisted by that helper.

Safety contract:
- ZERO Gemini/model calls and ZERO public-release actions.
- Private identity is accepted only from a verified note /notes/<id>/edit route.
- The opaque private draft id and 投稿準備中 are written in one fail-closed Notion PATCH.
- RSS is read-only public evidence of publication.
- Existing conflicting URL/date values are never overwritten.
- Duplicate queue titles or duplicate RSS titles fail closed.
- Content Intelligence 公開日 is source provenance, not note投稿日; reconciliation never mutates it.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests

import note_ready_sync as sync

NOTE_USER_NAME = os.environ.get("NOTE_USER_NAME", "trendhub_biz").strip()
RSS_TIMEOUT_SECONDS = 20
TOKYO = ZoneInfo("Asia/Tokyo")
DRAFT_ID_PROPERTY = "note下書きID"
PREPARING_STATUS = "投稿準備中"
_DRAFT_PATH = re.compile(r"^/notes/([^/?#]+)/edit/?$")


def draft_identity_from_url(draft_url: str, *, error_type: type[Exception] = RuntimeError) -> str:
    """Return only the opaque id from a confirmed note private edit route."""
    try:
        parsed = urlparse(str(draft_url or "").strip())
    except Exception as exc:
        raise error_type("verified note draft URL is invalid") from exc
    host = str(parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in {"note.com", "editor.note.com"}:
        raise error_type("verified note draft URL is not a note edit route")
    if parsed.params or parsed.query or parsed.fragment:
        raise error_type("verified note draft URL contains an unexpected suffix")
    match = _DRAFT_PATH.fullmatch(parsed.path or "")
    if not match:
        raise error_type("verified note draft URL is not a stable edit route")
    identity = match.group(1).strip()
    if not identity or len(identity) > 200 or not re.fullmatch(r"[A-Za-z0-9_-]+", identity):
        raise error_type("verified note draft identity is malformed")
    return identity


def validate_destination_contract(*, error_type: type[Exception] = RuntimeError) -> None:
    """Fail before browser mutation unless the private identity field exists with the right type."""
    response = sync._request(
        "GET",
        sync._schema_url(sync.DEST_DATA_SOURCE_ID, sync.DEST_DATABASE_ID),
    )
    if response.status_code != 200:
        raise error_type(f"note Ready identity schema fetch failed: HTTP {response.status_code}")
    props = response.json().get("properties") or {}
    prop = props.get(DRAFT_ID_PROPERTY) or {}
    if prop.get("type") != "rich_text":
        raise error_type("note Ready DB lacks the private draft identity contract")


def mark_draft_created(
    destination_page_id: str,
    draft_url: str,
    *,
    error_type: type[Exception] = RuntimeError,
) -> str:
    """Persist private identity and lifecycle state atomically in one page PATCH."""
    identity = draft_identity_from_url(draft_url, error_type=error_type)
    response = sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{destination_page_id}",
        json={
            "properties": {
                DRAFT_ID_PROPERTY: {
                    "rich_text": [{"type": "text", "text": {"content": identity}}]
                },
                "投稿状態": {"select": {"name": PREPARING_STATUS}},
            }
        },
    )
    if response.status_code != 200:
        raise error_type(
            f"Draft was created but private identity/status update failed: HTTP {response.status_code}"
        )
    return identity


def run_with_identity(base: Any, *, confirm: str, requested_sync_id: str = "", prepare_only: bool = False) -> dict[str, Any]:
    """Mirror the existing zero-model draft path while closing the stable-identity gap."""
    if confirm != base.CONFIRM_TOKEN:
        raise base.NoteDraftError(f"Confirmation must equal {base.CONFIRM_TOKEN}")

    validate_destination_contract(error_type=base.NoteDraftError)
    article = base._prepare_article(requested_sync_id)
    result: dict[str, Any] = {
        "success": True,
        "zero_gemini_calls": True,
        "sync_id": article["sync_id"],
        "status": "prepared" if prepare_only else "draft_created",
        "telegram_notified": False,
    }
    if prepare_only:
        return result

    eyecatch_path = base._download_eyecatch(
        article["eyecatch_url"], article["sync_id"], article["title"]
    )
    storage_path = base._decode_storage_state()
    try:
        draft_url = base._create_browser_draft(
            article["title"], article["manuscript"], eyecatch_path, storage_path
        )
    finally:
        storage_path.unlink(missing_ok=True)

    mark_draft_created(
        article["destination_page_id"],
        draft_url,
        error_type=base.NoteDraftError,
    )
    result["draft_url"] = draft_url
    result["telegram_notified"] = base._send_telegram_draft_notice(draft_url)
    return result


def install_draft_identity(base: Any) -> None:
    """Install only the B-2 private identity contract into the existing draft runner."""
    if getattr(base, "_p0b2_identity_installed", False):
        return

    def _run(*, confirm: str, requested_sync_id: str = "", prepare_only: bool = False) -> dict[str, Any]:
        return run_with_identity(
            base,
            confirm=confirm,
            requested_sync_id=requested_sync_id,
            prepare_only=prepare_only,
        )

    base.DRAFT_ID_PROPERTY = DRAFT_ID_PROPERTY
    base._draft_identity_from_url = lambda value: draft_identity_from_url(
        value, error_type=base.NoteDraftError
    )
    base._mark_draft_created = lambda page_id, value: mark_draft_created(
        page_id, value, error_type=base.NoteDraftError
    )
    base.run = _run
    base._p0b2_identity_installed = True


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def _canonical_public_url(value: str, user_name: str = NOTE_USER_NAME) -> str:
    value = str(value or "").strip()
    try:
        parts = urlsplit(value)
    except ValueError:
        return ""
    if parts.scheme != "https" or parts.netloc.lower() != "note.com":
        return ""
    expected = rf"/{re.escape(user_name)}/n/n[a-zA-Z0-9]+/?"
    if not re.fullmatch(expected, parts.path):
        return ""
    path = parts.path.rstrip("/")
    return urlunsplit(("https", "note.com", path, "", ""))


def _publication_date(value: str) -> str:
    try:
        dt = parsedate_to_datetime(str(value or "").strip())
    except (TypeError, ValueError, OverflowError):
        return ""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TOKYO).date().isoformat()


def _fetch_feed(user_name: str = NOTE_USER_NAME) -> list[dict[str, str]]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", user_name):
        raise ValueError("NOTE_USER_NAME is invalid")
    url = f"https://note.com/{user_name}/rss"
    response = requests.get(
        url,
        headers={"User-Agent": "AIIF-Publication-Reconciler/1.0 (+read-only RSS)"},
        timeout=RSS_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RuntimeError(f"note RSS fetch failed: HTTP {response.status_code}")
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise RuntimeError("note RSS response is not valid XML") from exc

    items: list[dict[str, str]] = []
    for item in root.findall("./channel/item"):
        title = _normalize_title(item.findtext("title") or "")
        public_url = _canonical_public_url(item.findtext("link") or "", user_name)
        published = _publication_date(item.findtext("pubDate") or "")
        if title and public_url and published:
            items.append({"title": title, "url": public_url, "published": published})
    return items


def _date(prop: dict | None) -> str:
    return str((((prop or {}).get("date") or {}).get("start")) or "").strip()


def _queue_row(page: dict) -> dict[str, str]:
    p = page.get("properties") or {}
    return {
        "page_id": str(page.get("id") or "").strip(),
        "sync_id": sync._normalize_page_id(sync._text(p.get("同期ID"))),
        "title": sync._text(p.get("記事タイトル")),
        "title_key": _normalize_title(sync._text(p.get("記事タイトル"))),
        "quality": sync._select(p.get("品質状態")),
        "posting": sync._select(p.get("投稿状態")),
        "public_url": _canonical_public_url(sync._url(p.get("note公開URL"))),
        "raw_public_url": sync._url(p.get("note公開URL")),
        "published": _date(p.get("投稿日")),
    }


def _source_identity(sync_id: str) -> dict[str, str]:
    response = sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
    if response.status_code != 200:
        raise RuntimeError(f"source page fetch failed for {sync_id}: HTTP {response.status_code}")
    page = response.json()
    if sync._normalize_page_id(page.get("id") or "") != sync_id:
        raise RuntimeError("source identity mismatch")
    p = page.get("properties") or {}
    return {
        "title": sync._text(p.get("note記事タイトル")) or sync._text(p.get("記事名")),
        "article_status": sync._select(p.get("記事状態")),
    }


def _patch_queue_publication(row: dict[str, str], item: dict[str, str], today: str) -> bool:
    existing_url = row["raw_public_url"]
    existing_date = row["published"]
    if existing_url:
        canonical_existing = _canonical_public_url(existing_url)
        if not canonical_existing or canonical_existing != item["url"]:
            raise RuntimeError("queue public URL conflicts with RSS")
    if existing_date and existing_date != item["published"]:
        raise RuntimeError("queue publication date conflicts with RSS")
    if row["posting"] == "投稿済み" and existing_url and existing_date:
        return False
    response = sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{row['page_id']}",
        json={"properties": {
            "投稿状態": {"select": {"name": "投稿済み"}},
            "note公開URL": {"url": item["url"]},
            "投稿日": {"date": {"start": item["published"]}},
            "最終同期日": {"date": {"start": today}},
        }},
    )
    if response.status_code != 200:
        raise RuntimeError(f"queue publication update failed: HTTP {response.status_code}")
    return True


def reconcile_publications(*, today: str | None = None) -> dict[str, Any]:
    if not sync.NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY (or NOTION_NOTE_READY_API_KEY) is required")
    if not (sync.DEST_DATA_SOURCE_ID or sync.DEST_DATABASE_ID):
        raise ValueError("note Ready destination DB is not configured")
    if not NOTE_USER_NAME:
        raise ValueError("NOTE_USER_NAME is required")
    today = today or datetime.now(TOKYO).date().isoformat()

    feed = _fetch_feed(NOTE_USER_NAME)
    feed_by_title: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in feed:
        feed_by_title[item["title"]].append(item)

    pages = sync._query_db(
        sync.DEST_DATA_SOURCE_ID,
        sync.DEST_DATABASE_ID,
        payload={"filter": {"and": [
            {"property": "品質状態", "select": {"equals": "Ready"}},
            {"or": [
                {"property": "投稿状態", "select": {"equals": "投稿準備中"}},
                {"property": "投稿状態", "select": {"equals": "投稿済み"}},
            ]},
        ]}},
    )
    rows = [_queue_row(page) for page in pages]
    active = [r for r in rows if r["page_id"] and r["sync_id"] and r["title_key"]]
    queue_by_title: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in active:
        queue_by_title[row["title_key"]].append(row)

    result: dict[str, Any] = {
        "feed_items": len(feed),
        "queue_candidates": len(active),
        "reconciled": 0,
        "already_reconciled": 0,
        "not_yet_public": 0,
        "ambiguous": 0,
        "conflict": 0,
        "source_updates": 0,
        "queue_updates": 0,
        "model_calls": 0,
        "public_release": False,
    }

    for title_key, title_rows in queue_by_title.items():
        matches = feed_by_title.get(title_key) or []
        if not matches:
            result["not_yet_public"] += len(title_rows)
            continue
        if len(title_rows) != 1 or len(matches) != 1:
            result["ambiguous"] += len(title_rows)
            continue
        row = title_rows[0]
        item = matches[0]
        try:
            source = _source_identity(row["sync_id"])
            if _normalize_title(source["title"]) != title_key:
                raise RuntimeError("source title does not match queue title")
            if source["article_status"] != "Ready":
                raise RuntimeError("source article is no longer Ready")
            if row["posting"] == "投稿済み":
                if not row["raw_public_url"] or not row["published"]:
                    raise RuntimeError("posted queue row is incomplete")
                if _canonical_public_url(row["raw_public_url"]) != item["url"] or row["published"] != item["published"]:
                    raise RuntimeError("posted queue row conflicts with RSS")
            queue_changed = _patch_queue_publication(row, item, today)
        except RuntimeError:
            result["conflict"] += 1
            continue
        result["source_updates"] += 0
        result["queue_updates"] += int(queue_changed)
        if queue_changed:
            result["reconciled"] += 1
        else:
            result["already_reconciled"] += 1
    return result


if __name__ == "__main__":
    print(json.dumps(reconcile_publications(), ensure_ascii=False, sort_keys=True))
