#!/usr/bin/env python3
"""Resync one existing private note draft body to the current Ready manuscript only.

Generic Production form of the proven 2026-09-27 exact-draft repair lanes.

Safety contract:
- exact 32-hex Content Intelligence sync_id only;
- an existing unpublished note queue row must already exist;
- source manuscript must already satisfy the current Publication Contract;
- source eyecatch must already satisfy the current Eyecatch Contract;
- destination may be Ready or Ready取消, but must remain 投稿準備中 and unpublished;
- the existing note draft is matched by exact title and must resolve to one edit route;
- only the existing draft body is rewritten to the approved current presentation;
- title is kept identical;
- existing eyecatch must remain present and unchanged;
- no new draft, no public release, zero Gemini calls;
- source manuscript bytes are never mutated/restamped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import eyecatch_publication_contract as eyecatch_contract
import note_draft_automation as note_base
import note_eyecatch_persistence as eyecatch
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as run190
import run193_note_official_header_upload as official_image
import run291_note_private_draft_audit as audit_base
import run417_note_body_verification as run417

CONFIRM_TOKEN = "RESYNC_READY_NOTE_BODY"


class ReadyNoteBodyResyncError(RuntimeError):
    pass


def _normalize_sync_id(value: str) -> str:
    raw = str(value or "")
    if re.fullmatch(r"[0-9a-fA-F]{32}", raw) is None:
        raise ReadyNoteBodyResyncError("sync_id must be exactly 32 hex characters")
    return raw.lower()


def _route_key(url: str) -> str:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    return f"{parsed.scheme.lower()}://{host}{parsed.path.rstrip('/')}"


def _same_edit_route(left: str, right: str) -> bool:
    if not audit_base._is_note_edit_url(left) or not audit_base._is_note_edit_url(right):
        return False
    return _route_key(left) == _route_key(right)


def _destination_private_row(sync_id: str) -> dict[str, Any]:
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": sync_id}}},
    )
    exact = [
        page for page in pages
        if ready_sync._normalize_page_id(
            ready_sync._text((page.get("properties") or {}).get("同期ID"))
        ) == sync_id
    ]
    if len(exact) != 1:
        raise ReadyNoteBodyResyncError("expected exactly one existing note Ready destination row")
    page = exact[0]
    props = page.get("properties") or {}
    quality = ready_sync._select(props.get("品質状態"))
    posting = ready_sync._select(props.get("投稿状態"))
    title = ready_sync._text(props.get("記事タイトル"))
    published = str((((props.get("投稿日") or {}).get("date") or {}).get("start")) or "").strip()
    if posting != "投稿準備中":
        raise ReadyNoteBodyResyncError(f"destination is not 投稿準備中: {posting!r}")
    if quality not in {"Ready", "Ready取消"}:
        raise ReadyNoteBodyResyncError(f"unexpected destination quality state: {quality!r}")
    if ready_sync._url(props.get("note公開URL")) or published:
        raise ReadyNoteBodyResyncError("destination has public-post evidence; refusing private-draft repair")
    if not title:
        raise ReadyNoteBodyResyncError("destination title is missing")
    return {
        "destination_page_id": str(page.get("id") or ""),
        "sync_id": sync_id,
        "title": title,
        "quality_state": quality,
        "posting_state": posting,
    }


def _source_current_article(sync_id: str, destination_title: str) -> dict[str, Any]:
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
    if response.status_code != 200:
        raise ReadyNoteBodyResyncError(
            f"Content Intelligence source fetch failed: HTTP {response.status_code}"
        )
    page = response.json()
    state = ready_sync._source_state(page)
    if state is None or state.get("sync_id") != sync_id:
        raise ReadyNoteBodyResyncError("Content Intelligence source is not an exact active Ready row")
    title = str(state.get("title") or "").strip()
    if title != str(destination_title or "").strip():
        raise ReadyNoteBodyResyncError("source and destination titles do not match")
    manuscript = ready_sync._source_current_ready_manuscript(sync_id)
    if not manuscript:
        raise ReadyNoteBodyResyncError("source manuscript is not current under the Publication Contract")
    image_url = str(state.get("eyecatch_url") or "").strip()
    try:
        eyecatch_contract.require_current_asset_url(image_url, title)
    except eyecatch_contract.EyecatchContractError as exc:
        raise ReadyNoteBodyResyncError("source eyecatch is not current under the Eyecatch Contract") from exc
    presented = audit_base.run222.prepare_note_editor_manuscript(manuscript, title)
    if len(presented) < 200:
        raise ReadyNoteBodyResyncError("prepared current note presentation is unexpectedly short")
    return {
        "sync_id": sync_id,
        "title": title,
        "manuscript": presented,
        "canonical_sha256": hashlib.sha256(manuscript.encode("utf-8")).hexdigest(),
        "eyecatch_url": image_url,
    }


def preflight(sync_id: str) -> dict[str, Any]:
    sync_id = _normalize_sync_id(sync_id)
    destination_before = _destination_private_row(sync_id)
    article = _source_current_article(sync_id, str(destination_before["title"]))

    # Only after the source is proven current may the exact automated quality state
    # be reconciled. Human posting state/publication evidence remain protected.
    sync_result = ready_sync.sync_note_ready_db(target_sync_id=sync_id)
    if int(sync_result.get("source_ready") or 0) != 1:
        raise ReadyNoteBodyResyncError("exact note Ready reconciliation did not preserve one current source")

    destination_after = _destination_private_row(sync_id)
    if destination_after["quality_state"] != "Ready":
        raise ReadyNoteBodyResyncError("exact destination reconciliation did not restore quality=Ready")
    if destination_after["posting_state"] != "投稿準備中":
        raise ReadyNoteBodyResyncError("posting state changed during exact destination reconciliation")

    return {
        **article,
        "destination_page_id": destination_after["destination_page_id"],
        "quality_state_before": destination_before["quality_state"],
        "quality_state": "Ready",
        "posting_state": "投稿準備中",
        "destination_exact_resync": True,
    }


def _cover_identity(page: Any) -> str:
    existing = official_image._find_existing_cover(page)
    if existing is None:
        raise ReadyNoteBodyResyncError("existing private draft has no uniquely identifiable cover")
    cover, _ = existing
    try:
        src = str(cover.evaluate("el => el.currentSrc || el.src || ''") or "")
    except Exception as exc:
        raise ReadyNoteBodyResyncError("existing cover media identity could not be read") from exc
    if not src:
        raise ReadyNoteBodyResyncError("existing cover media identity is empty")
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def _find_exact_existing_draft(page: Any, profile: Any, title: str) -> str:
    candidates = audit_base._recent_private_edit_urls(profile)
    if not candidates:
        raise ReadyNoteBodyResyncError("no existing private note edit route is present in Chrome history")

    matched: dict[str, str] = {}
    seeded = False
    for candidate in candidates:
        try:
            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if note_base._looks_logged_out(page) and not seeded:
                seeded = bool(run190._seed_note_state(page.context, page))
                if seeded:
                    page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(900)
            if note_base._looks_logged_out(page):
                continue
            if not audit_base._is_note_edit_url(str(page.url or "")):
                continue
            if audit_base._title_value(page) != title.strip():
                continue
            actual = str(page.url or "")
            matched[_route_key(actual)] = actual
        except Exception:
            continue

    if len(matched) != 1:
        raise ReadyNoteBodyResyncError(
            f"expected exactly one existing private draft with the approved title; found {len(matched)}"
        )
    return next(iter(matched.values()))


def _apply_existing_body(article: dict[str, Any]) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ReadyNoteBodyResyncError("Playwright is required for existing draft body resync") from exc

    run190.install()
    run417.install(note_base)
    official_image.install()
    profile = run190._profile_dir()

    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route = _find_exact_existing_draft(page, profile, str(article["title"]))
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if not _same_edit_route(route, str(page.url or "")):
                raise ReadyNoteBodyResyncError("existing draft route changed before mutation")
            if audit_base._title_value(page) != str(article["title"]).strip():
                raise ReadyNoteBodyResyncError("existing draft title changed before mutation")

            old_cover_identity = _cover_identity(page)

            title_field = note_base._set_title(page, str(article["title"]))
            body = note_base._find_body(page, title_field)
            note_base._paste_manuscript(page, body, str(article["manuscript"]))
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, str(article["manuscript"]))

            saved = note_base._save_draft_and_verify(
                page,
                str(article["title"]),
                str(article["manuscript"]),
                image_required=True,
            )
            if not _same_edit_route(route, saved):
                raise ReadyNoteBodyResyncError("body resync escaped the existing private draft route")

            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if not _same_edit_route(route, str(page.url or "")):
                raise ReadyNoteBodyResyncError("draft route changed after persistence reload")

            audit = audit_base._audit_current_page(
                page,
                str(article["title"]),
                str(article["manuscript"]),
            )
            if audit_base._title_value(page) != str(article["title"]).strip():
                raise ReadyNoteBodyResyncError("title changed during body resync")

            new_cover_identity = _cover_identity(page)
            if new_cover_identity != old_cover_identity:
                raise ReadyNoteBodyResyncError("eyecatch changed during body-only resync")

            metrics = eyecatch.collect_eyecatch_metrics(
                page,
                title_locator=note_base._find_title(page),
            )
            if not eyecatch.eyecatch_persistence_confirmed(metrics):
                raise ReadyNoteBodyResyncError("existing eyecatch persistence proof failed")

            return {
                "status": "ready_note_body_resynced",
                "sync_id": article["sync_id"],
                "same_edit_route": True,
                "title_unchanged": True,
                "body_verified": True,
                "eyecatch_unchanged": True,
                "persisted_after_reload": True,
                "new_draft_created": False,
                "public_release": False,
                "zero_gemini_calls": True,
                "article_regeneration": False,
                "source_manuscript_mutation": False,
                "editor_route_hash": hashlib.sha256(_route_key(route).encode("utf-8")).hexdigest()[:12],
                "heading_count": audit.get("heading_count"),
                "paragraph_count": audit.get("paragraph_count"),
            }
        finally:
            context.close()


def run(*, confirm: str, sync_id: str, prepare_only: bool = False) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise ReadyNoteBodyResyncError(f"confirmation must equal {CONFIRM_TOKEN}")
    article = preflight(sync_id)
    result: dict[str, Any] = {
        "success": True,
        "status": "body_resync_ready" if prepare_only else "ready_note_body_resynced",
        "sync_id": article["sync_id"],
        "quality_state_before": article["quality_state_before"],
        "quality_state": article["quality_state"],
        "posting_state": article["posting_state"],
        "current_asset_url": True,
        "zero_gemini_calls": True,
        "new_draft_created": False,
        "public_release": False,
        "article_regeneration": False,
        "source_manuscript_mutation": False,
    }
    if prepare_only:
        result["should_start_vm"] = True
        return result
    result.update(_apply_existing_body(article))
    destination_after = _destination_private_row(str(article["sync_id"]))
    if destination_after["quality_state"] != "Ready" or destination_after["posting_state"] != "投稿準備中":
        raise ReadyNoteBodyResyncError("queue state changed after body-only resync")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", default=os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    parser.add_argument("--confirm", default=os.environ.get("NOTE_BODY_RESYNC_CONFIRM", ""))
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        default=os.environ.get("NOTE_BODY_RESYNC_PREPARE_ONLY", "false").lower() in {"1", "true", "yes", "on"},
    )
    parser.add_argument("--result-file", default=os.environ.get("NOTE_BODY_RESYNC_RESULT_FILE", ""))
    args = parser.parse_args()
    result = run(confirm=args.confirm, sync_id=args.sync_id, prepare_only=args.prepare_only)
    if args.result_file:
        from pathlib import Path
        target = Path(args.result_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
