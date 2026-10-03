#!/usr/bin/env python3
"""P0-B2: bind a verified private note draft identity to its queue row.

The normal note editor exposes a stable edit route after autosave.  This module keeps only
its opaque draft identifier in the private Note Ready DB and advances 投稿状態 to 投稿準備中
in the same Notion PATCH.  Raw private draft URLs are never logged or persisted here.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import note_ready_sync as ready_sync

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
    response = ready_sync._request(
        "GET",
        ready_sync._schema_url(ready_sync.DEST_DATA_SOURCE_ID, ready_sync.DEST_DATABASE_ID),
    )
    if response.status_code != 200:
        raise error_type(
            f"note Ready identity schema fetch failed: HTTP {response.status_code}"
        )
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
    """Persist identity and lifecycle state atomically in one page PATCH."""
    identity = draft_identity_from_url(draft_url, error_type=error_type)
    response = ready_sync._request(
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
    """Mirror the existing zero-model run path while closing the identity gap."""
    if confirm != base.CONFIRM_TOKEN:
        raise base.NoteDraftError(f"Confirmation must equal {base.CONFIRM_TOKEN}")

    # Check the external storage contract before any note/browser mutation.
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


def install(base: Any) -> None:
    """Install only the B-2 run contract; all browser/presentation patches remain untouched."""
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
