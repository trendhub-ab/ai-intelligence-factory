#!/usr/bin/env python3
"""Apply the current production eyecatch to one existing private note draft only.

This is the generic Production form of the 2026-09-27 proven cover-replacement lane.

Safety contract:
- exact Content Intelligence sync_id only;
- source and destination must already be current Ready / 投稿準備中;
- source manuscript must already satisfy the current Publication Contract;
- source eyecatch must already satisfy the current Eyecatch Contract;
- exactly one existing private note edit route must match title *and* approved body;
- title/body are never rewritten;
- no new note draft is created and no public release action exists;
- failure after cover mutation attempts a best-effort rollback to the previous cover.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import eyecatch_publication_contract as eyecatch_contract
import note_draft_automation as note_base
import note_eyecatch_persistence as eyecatch
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as run190
import run193_note_official_header_upload as official_image
import run291_note_private_draft_audit as audit_base

CONFIRM_TOKEN = "APPLY_READY_NOTE_COVER"
RUNTIME_DIR = Path(".runtime/ready-note-cover")


class ReadyNoteCoverError(RuntimeError):
    pass


def _normalize_sync_id(value: str) -> str:
    sync_id = re.sub(r"[^0-9a-fA-F]", "", str(value or "")).lower()
    if len(sync_id) != 32:
        raise ReadyNoteCoverError("sync_id must be exactly 32 hex characters")
    return sync_id


def _route_key(url: str) -> str:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    return f"{parsed.scheme.lower()}://{host}{parsed.path.rstrip('/')}"


def _same_edit_route(left: str, right: str) -> bool:
    if not audit_base._is_note_edit_url(left) or not audit_base._is_note_edit_url(right):
        return False
    return _route_key(left) == _route_key(right)


def _source_current_asset(sync_id: str, title: str) -> tuple[str, str]:
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
    if response.status_code != 200:
        raise ReadyNoteCoverError(f"Content Intelligence source fetch failed: HTTP {response.status_code}")
    page = response.json()
    state = ready_sync._source_state(page)
    if state is None or state.get("sync_id") != sync_id:
        raise ReadyNoteCoverError("Content Intelligence source is not an exact active Ready row")
    if str(state.get("title") or "").strip() != str(title or "").strip():
        raise ReadyNoteCoverError("source and destination titles do not match")
    manuscript = ready_sync._source_current_ready_manuscript(sync_id)
    if not manuscript:
        raise ReadyNoteCoverError("source manuscript is not current under the Publication Contract")
    image_url = str(state.get("eyecatch_url") or "").strip()
    try:
        eyecatch_contract.require_current_asset_url(image_url, title)
    except eyecatch_contract.EyecatchContractError as exc:
        raise ReadyNoteCoverError("source eyecatch is not current under the Eyecatch Contract") from exc
    return image_url, manuscript


def _destination_private_row(sync_id: str) -> dict[str, Any]:
    """Read the exact existing queue row without requiring automated quality=Ready yet."""
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
        raise ReadyNoteCoverError("expected exactly one existing note Ready destination row")
    page = exact[0]
    props = page.get("properties") or {}
    posting = ready_sync._select(props.get("投稿状態"))
    quality = ready_sync._select(props.get("品質状態"))
    title = ready_sync._text(props.get("記事タイトル"))
    published = str((((props.get("投稿日") or {}).get("date") or {}).get("start")) or "").strip()
    if posting != "投稿準備中":
        raise ReadyNoteCoverError(f"existing destination is not 投稿準備中: {posting!r}")
    if quality not in {"Ready", "Ready取消"}:
        raise ReadyNoteCoverError(f"unexpected destination quality state: {quality!r}")
    if ready_sync._url(props.get("note公開URL")) or published:
        raise ReadyNoteCoverError("destination has public-post evidence; cover-only apply refuses it")
    if not title:
        raise ReadyNoteCoverError("destination title is missing")
    return {
        "destination_page_id": str(page.get("id") or ""),
        "sync_id": sync_id,
        "title": title,
        "quality_state_before": quality,
        "posting_state": posting,
    }


def preflight(sync_id: str) -> dict[str, Any]:
    sync_id = _normalize_sync_id(sync_id)

    # Require an already-existing private-draft queue row before any synchronization.
    # This prevents an eyecatch apply request from creating a new publication candidate.
    destination_before = _destination_private_row(sync_id)

    # Prove the source manuscript and eyecatch are already current. Only after those
    # publication prerequisites pass may the exact destination's automated quality
    # status be reconciled. Human posting fields are preserved by note_ready_sync.
    source_response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
    if source_response.status_code != 200:
        raise ReadyNoteCoverError(
            f"Content Intelligence source fetch failed: HTTP {source_response.status_code}"
        )
    source_state = ready_sync._source_state(source_response.json())
    if source_state is None or source_state.get("sync_id") != sync_id:
        raise ReadyNoteCoverError("Content Intelligence source is not an exact active Ready row")
    source_title = str(source_state.get("title") or "").strip()
    if source_title != str(destination_before["title"]).strip():
        raise ReadyNoteCoverError("source and destination titles do not match")

    image_url, canonical_manuscript = _source_current_asset(sync_id, source_title)

    sync_result = ready_sync.sync_note_ready_db(target_sync_id=sync_id)
    if int(sync_result.get("source_ready") or 0) != 1:
        raise ReadyNoteCoverError("exact note Ready reconciliation did not preserve one current source")

    article = audit_base._expected_article(sync_id)
    destination_after = audit_base._destination_row(sync_id)
    return {
        **article,
        "sync_id": sync_id,
        "eyecatch_url": image_url,
        "canonical_body_sha256": hashlib.sha256(canonical_manuscript.encode("utf-8")).hexdigest(),
        "quality_state": "Ready",
        "quality_state_before": destination_before["quality_state_before"],
        "posting_state": destination_after["posting_state"] if "posting_state" in destination_after else "投稿準備中",
        "destination_page_id": destination_after["destination_page_id"],
        "destination_exact_resync": True,
    }


def _visible_body_hash(page: Any) -> str:
    title_field = note_base._find_title(page)
    body = note_base._find_body(page, title_field)
    try:
        text = str(body.inner_text(timeout=5000) or "")
    except Exception as exc:
        raise ReadyNoteCoverError("could not read existing note body") from exc
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        raise ReadyNoteCoverError("existing note body is empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _header_media_identity(page: Any) -> str:
    existing = official_image._find_existing_cover(page)
    if existing is None:
        raise ReadyNoteCoverError("existing private draft has no uniquely identifiable cover")
    cover, _ = existing
    try:
        src = str(cover.evaluate("el => el.currentSrc || el.src || ''") or "")
    except Exception as exc:
        raise ReadyNoteCoverError("existing cover media identity could not be read") from exc
    if not src:
        raise ReadyNoteCoverError("existing cover media identity is empty")
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def _cover_changed(page: Any, old_identity: str) -> bool:
    try:
        return _header_media_identity(page) != old_identity
    except ReadyNoteCoverError:
        return False


def _backup_current_cover(page: Any, sync_id: str) -> Path:
    existing = official_image._find_existing_cover(page)
    if existing is None:
        raise ReadyNoteCoverError("existing private draft has no cover to replace")
    cover, _ = existing
    src = str(cover.evaluate("el => el.currentSrc || el.src || ''") or "")
    if not src.startswith("https://"):
        raise ReadyNoteCoverError("existing note cover is not downloadable HTTPS")
    response = page.request.get(src, timeout=30000)
    if not response.ok:
        raise ReadyNoteCoverError(f"existing note cover backup failed: HTTP {response.status}")
    body = response.body()
    if len(body) < 1024:
        raise ReadyNoteCoverError("existing note cover backup is unexpectedly small")
    content_type = str(response.headers.get("content-type") or "").lower()
    suffix = ".png"
    if "jpeg" in content_type or "jpg" in content_type:
        suffix = ".jpg"
    elif "webp" in content_type:
        suffix = ".webp"
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNTIME_DIR / f"{sync_id}-before{suffix}"
    path.write_bytes(body)
    return path


def _find_exact_existing_draft(page: Any, profile: Path, article: dict[str, Any]) -> str:
    candidates = audit_base._recent_private_edit_urls(profile)
    if not candidates:
        raise ReadyNoteCoverError("no existing private note edit route is present in Chrome history")

    matched: dict[str, str] = {}
    title_conflicts = 0
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
            if audit_base._title_value(page) != str(article["title"]).strip():
                continue
            try:
                audit_base._audit_current_page(
                    page,
                    str(article["title"]),
                    str(article["manuscript"]),
                )
            except audit_base.PrivateDraftAuditError:
                title_conflicts += 1
                continue
            actual = str(page.url or "")
            matched[_route_key(actual)] = actual
        except ReadyNoteCoverError:
            raise
        except Exception:
            continue

    if len(matched) != 1:
        if title_conflicts and not matched:
            raise ReadyNoteCoverError(
                "a private draft with the target title exists but its body is not the approved current article"
            )
        raise ReadyNoteCoverError(
            f"expected exactly one approved existing private draft; found {len(matched)}"
        )
    return next(iter(matched.values()))


def _restore_backup(page: Any, backup_path: Path, article: dict[str, Any]) -> bool:
    if not backup_path.is_file():
        return False
    try:
        official_image._upload_header_image(page, backup_path)
        note_base._save_draft_and_verify(
            page,
            str(article["title"]),
            str(article["manuscript"]),
            image_required=True,
        )
        return True
    except Exception:
        return False


def _apply_to_existing_draft(article: dict[str, Any], image_path: Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ReadyNoteCoverError("Playwright is required for note cover apply") from exc

    run190.install()
    official_image.install()
    profile = run190._profile_dir()

    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        backup_path: Path | None = None
        changed_started = False
        try:
            route = _find_exact_existing_draft(page, profile, article)
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if not _same_edit_route(route, str(page.url or "")):
                raise ReadyNoteCoverError("existing draft route changed before mutation")

            before_metrics = audit_base._audit_current_page(
                page,
                str(article["title"]),
                str(article["manuscript"]),
            )
            before_body_hash = _visible_body_hash(page)
            old_identity = _header_media_identity(page)
            backup_path = _backup_current_cover(page, str(article["sync_id"]))

            changed_started = True
            official_image._upload_header_image(
                page,
                image_path,
                media_changed=lambda: _cover_changed(page, old_identity),
            )

            saved = note_base._save_draft_and_verify(
                page,
                str(article["title"]),
                str(article["manuscript"]),
                image_required=True,
            )
            if not _same_edit_route(route, saved):
                raise ReadyNoteCoverError("cover apply escaped the existing private draft route")

            new_identity = _header_media_identity(page)
            if new_identity == old_identity:
                raise ReadyNoteCoverError("current production eyecatch did not replace the previous cover")

            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if not _same_edit_route(route, str(page.url or "")):
                raise ReadyNoteCoverError("draft route changed after cover persistence reload")

            after_metrics = audit_base._audit_current_page(
                page,
                str(article["title"]),
                str(article["manuscript"]),
            )
            after_body_hash = _visible_body_hash(page)
            if after_body_hash != before_body_hash:
                raise ReadyNoteCoverError("note body changed during cover-only apply")
            if audit_base._title_value(page) != str(article["title"]).strip():
                raise ReadyNoteCoverError("note title changed during cover-only apply")

            persisted_identity = _header_media_identity(page)
            if persisted_identity != new_identity:
                raise ReadyNoteCoverError("production eyecatch did not persist after reload")

            metrics = eyecatch.collect_eyecatch_metrics(
                page,
                title_locator=note_base._find_title(page),
            )
            if not eyecatch.eyecatch_persistence_confirmed(metrics):
                raise ReadyNoteCoverError("shared eyecatch persistence proof failed")

            return {
                "status": "ready_note_cover_applied",
                "sync_id": article["sync_id"],
                "same_edit_route": True,
                "title_unchanged": True,
                "body_unchanged": True,
                "body_visible_sha256": after_body_hash,
                "eyecatch_identity_changed": True,
                "persisted_after_reload": True,
                "new_draft_created": False,
                "public_release": False,
                "note_mutation_scope": "cover_only",
                "editor_route_hash": hashlib.sha256(_route_key(route).encode()).hexdigest()[:12],
                "before_audit": {
                    "heading_count": before_metrics.get("heading_count"),
                    "paragraph_count": before_metrics.get("paragraph_count"),
                },
                "after_audit": {
                    "heading_count": after_metrics.get("heading_count"),
                    "paragraph_count": after_metrics.get("paragraph_count"),
                },
            }
        except Exception:
            if changed_started and backup_path is not None:
                _restore_backup(page, backup_path, article)
            raise
        finally:
            if backup_path is not None:
                backup_path.unlink(missing_ok=True)
            context.close()


def run(*, confirm: str, sync_id: str, prepare_only: bool = False) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise ReadyNoteCoverError(f"confirmation must equal {CONFIRM_TOKEN}")
    article = preflight(sync_id)
    result: dict[str, Any] = {
        "success": True,
        "status": "cover_apply_ready" if prepare_only else "ready_note_cover_applied",
        "sync_id": article["sync_id"],
        "current_asset_url": True,
        "quality_state_preserved": article["quality_state"],
        "posting_state_preserved": article["posting_state"],
        "zero_gemini_calls": True,
        "new_draft_created": False,
        "public_release": False,
        "article_regeneration": False,
        "source_manuscript_mutation": False,
    }
    if prepare_only:
        result["should_start_vm"] = True
        return result

    image_path = note_base._download_eyecatch(
        str(article["eyecatch_url"]),
        str(article["sync_id"]),
        str(article["title"]),
    )
    try:
        result.update(_apply_to_existing_draft(article, image_path))
    finally:
        image_path.unlink(missing_ok=True)

    # Re-prove the publication queue state after the note-only cover mutation.
    destination_after = audit_base._destination_row(str(article["sync_id"]))
    if str(destination_after.get("title") or "") != str(article["title"]):
        raise ReadyNoteCoverError("destination title changed during cover-only apply")
    result["quality_state_preserved"] = "Ready"
    result["posting_state_preserved"] = "投稿準備中"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", default=os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    parser.add_argument("--confirm", default=os.environ.get("NOTE_COVER_APPLY_CONFIRM", ""))
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        default=os.environ.get("NOTE_COVER_PREPARE_ONLY", "false").lower() in {"1", "true", "yes", "on"},
    )
    parser.add_argument("--result-file", default=os.environ.get("NOTE_COVER_RESULT_FILE", ""))
    args = parser.parse_args()
    result = run(confirm=args.confirm, sync_id=args.sync_id, prepare_only=args.prepare_only)
    if args.result_file:
        target = Path(args.result_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
