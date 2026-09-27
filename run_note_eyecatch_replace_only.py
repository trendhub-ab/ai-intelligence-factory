#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from PIL import Image
from playwright.sync_api import sync_playwright

import note_draft_automation as note_base
import editorial_eyecatch as editorial
import run180_eyecatch_semantic_layout as run180
import run190_note_persistent_cloud as run190
import run193_note_official_header_upload as upload
import run_vtcode_existing_draft_repair as repair

SUMMARY = "VT CodeはAIによるコード変更をレビューし、変更内容を確認するためのコーディングエージェントです。"
RUNTIME_DIR = Path(".runtime/eyecatch-replace-only")
NEW_IMAGE = RUNTIME_DIR / "vtcode-replacement.png"
BACKUP_IMAGE = RUNTIME_DIR / "vtcode-before-replacement.png"


class ReplaceError(RuntimeError):
    pass


def _unique_cover(page: Any) -> tuple[Any, dict[str, float]]:
    title_box = note_base._find_title(page).bounding_box()
    if not title_box:
        raise ReplaceError("title geometry unavailable")
    images = page.locator("img")
    matched: list[tuple[Any, dict[str, float]]] = []
    for i in range(min(images.count(), 80)):
        item = images.nth(i)
        try:
            box = item.bounding_box()
            if not item.is_visible(timeout=120) or not box:
                continue
            if float(box["width"]) >= 420 and float(box["height"]) >= 140 and float(box["y"]) < float(title_box["y"]):
                matched.append((item, box))
        except Exception:
            continue
    if len(matched) != 1:
        raise ReplaceError(f"expected one existing cover image; found {len(matched)}")
    return matched[0]


def _backup_cover(page: Any, cover: Any) -> str:
    src = str(cover.evaluate("el => el.currentSrc || el.src || ''") or "")
    if not src.startswith("https://"):
        raise ReplaceError("existing cover source is not downloadable HTTPS")
    response = page.request.get(src, timeout=30000)
    if not response.ok:
        raise ReplaceError(f"existing cover backup failed: HTTP {response.status}")
    body = response.body()
    if len(body) < 1024:
        raise ReplaceError("existing cover backup is unexpectedly small")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_IMAGE.write_bytes(body)
    return src


def _cover_delete_control(page: Any, cover_box: dict[str, float]) -> Any:
    # Current note official replacement flow removes an uploaded cover first.
    # Live evidence exposes that action as aria-label=削除 in the cover toolbar.
    controls = page.locator('button[aria-label="削除"], [role="button"][aria-label="削除"]')
    matched: list[Any] = []
    top = float(cover_box["y"]) - 180.0
    bottom = float(cover_box["y"]) + float(cover_box["height"])
    for i in range(min(controls.count(), 20)):
        item = controls.nth(i)
        try:
            if not item.is_visible(timeout=150):
                continue
            box = item.bounding_box()
            if not box:
                continue
            cy = float(box["y"]) + float(box["height"]) / 2.0
            if top <= cy <= bottom and 20 <= float(box["width"]) <= 90 and 20 <= float(box["height"]) <= 90:
                matched.append(item)
        except Exception:
            continue
    if len(matched) != 1:
        raise ReplaceError(f"cover delete control is ambiguous; found {len(matched)}")
    return matched[0]


def _wait_cover_gone(page: Any, old_identity: str) -> None:
    deadline = time.time() + 12
    while time.time() < deadline:
        try:
            current = repair._header_media_identity(page)
        except Exception:
            return
        if current != old_identity:
            return
        page.wait_for_timeout(250)
    raise ReplaceError("existing cover did not disappear after delete")


def _generate_replacement() -> dict[str, Any]:
    """Create a provider-free test cover; this experiment tests replacement UI only."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    clean_title = repair.NEW_TITLE.strip()
    if not clean_title or "..." in clean_title or "…" in clean_title:
        raise ReplaceError("test cover title is invalid")
    category = editorial.infer_editorial_category(clean_title, SUMMARY, "HackerNews")
    editorial.generate_note_editorial_eyecatch(
        clean_title, SUMMARY, str(NEW_IMAGE), category=category
    )
    with Image.open(NEW_IMAGE) as image:
        if image.size != (1280, 670):
            raise ReplaceError(f"replacement image has wrong size: {image.size}")
    return {
        "eyecatch_title": clean_title,
        "category": category,
        "size": [1280, 670],
        "zero_provider_calls": True,
        "purpose": "replacement_ui_only",
    }

def _restore_backup(page: Any, title: str, body_manuscript: str, old_identity: str) -> bool:
    try:
        # Restore only when the replacement left the cover absent or changed.
        try:
            current = repair._header_media_identity(page)
        except Exception:
            current = ""
        if current == old_identity:
            return True
        upload._upload_header_image(
            page, BACKUP_IMAGE,
            media_changed=lambda: repair._cover_changed(page, current or old_identity),
        )
        note_base._save_draft_and_verify(page, title, body_manuscript, image_required=True)
        return True
    except Exception:
        return False


def replace_existing_cover_only() -> dict[str, Any]:
    generated = _generate_replacement()
    manuscript = repair.load_manuscript()
    body_manuscript = note_base._body_manuscript_for_note(repair.NEW_TITLE, manuscript)
    run190.install()
    profile = run190._profile_dir()

    with sync_playwright() as p:
        context = run190._launch_persistent_context(p)
        page = context.new_page()
        page.set_default_timeout(30000)
        old_identity = ""
        deleted = False
        try:
            url = repair._open_exact_draft(page, profile)
            before_title = repair.audit_base._title_value(page)
            if before_title != repair.NEW_TITLE:
                raise ReplaceError("unexpected draft title before replacement")
            body = note_base._find_body(page, note_base._find_title(page))
            note_base._verify_body_content(body, body_manuscript)

            cover, cover_box = _unique_cover(page)
            old_identity = repair._header_media_identity(page)
            _backup_cover(page, cover)

            # Activate the existing cover context before selecting its explicit delete action.
            cover.click()
            page.wait_for_timeout(350)
            delete = _cover_delete_control(page, cover_box)
            delete.click()
            deleted = True
            _wait_cover_gone(page, old_identity)

            # Official note flow: after removal, use the same proven new-cover upload flow.
            upload._upload_header_image(
                page, NEW_IMAGE,
                media_changed=lambda: repair._cover_changed(page, old_identity),
            )
            saved = note_base._save_draft_and_verify(
                page, repair.NEW_TITLE, body_manuscript, image_required=True
            )
            if not repair._same_edit_route(url, saved):
                raise ReplaceError("replacement escaped the existing private draft route")
            new_identity = repair._header_media_identity(page)
            if new_identity == old_identity:
                raise ReplaceError("cover media identity did not change")

            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if repair.audit_base._title_value(page) != repair.NEW_TITLE:
                raise ReplaceError("title changed after cover replacement")
            body = note_base._find_body(page, note_base._find_title(page))
            note_base._verify_body_content(body, body_manuscript)
            persisted_identity = repair._header_media_identity(page)
            if persisted_identity != new_identity:
                raise ReplaceError("replacement cover did not persist after reload")

            return {
                "status": "existing_cover_replaced_and_persisted",
                "official_flow": "delete_then_readd",
                "same_edit_route": True,
                "title_unchanged": True,
                "body_unchanged": True,
                "old_identity_changed": True,
                "persisted_after_reload": True,
                "new_draft_created": False,
                "public_release": False,
                "generated": generated,
            }
        except Exception:
            if deleted and old_identity and BACKUP_IMAGE.is_file():
                _restore_backup(page, repair.NEW_TITLE, body_manuscript, old_identity)
            raise
        finally:
            context.close()


if __name__ == "__main__":
    print(json.dumps(replace_existing_cover_only(), ensure_ascii=False, sort_keys=True))
