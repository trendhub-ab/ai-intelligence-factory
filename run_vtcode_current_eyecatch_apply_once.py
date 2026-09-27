#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

import eyecatch_publication_contract as eyecatch_contract
import note_draft_automation as note_base
import note_eyecatch_persistence as eyecatch
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as run190
import run193_note_official_header_upload as official_image
import run_vtcode_existing_draft_repair as repair

IMAGE_URL = "https://raw.githubusercontent.com/trendhub-ab/ai-intelligence-factory/runtime-state/eyecatch_images/vtcode-production-eyecatch__ecv1_988cce2b4aaaded6.png"
BACKUP = Path(".runtime/vtcode-before-current-eyecatch.png")


class ApplyError(RuntimeError):
    pass


def _restamp_current_manuscript_bytes() -> None:
    """Re-stamp the exact approved manuscript under the current publication policy.

    This changes provenance only. The manuscript bytes are preserved exactly; the
    historical newline-aware chunker is deliberately not used here because it can
    mutate bytes at chunk boundaries.
    """
    manuscript = repair.load_manuscript()
    if ready_sync._source_current_ready_manuscript(repair.SYNC_ID) == manuscript:
        return
    caption = repair.publication_contract.current_ready_caption(manuscript)
    chunks = lambda text: [text[i:i + 1800] for i in range(0, len(text), 1800)]
    children = repair.build_notion_manuscript_children(
        manuscript,
        caption,
        chunker=chunks,
    )
    response = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{repair.SYNC_ID}/children",
        json={"children": children},
    )
    if response.status_code != 200:
        raise ApplyError(f"current manuscript provenance restamp failed: HTTP {response.status_code}")
    if ready_sync._source_current_ready_manuscript(repair.SYNC_ID) != manuscript:
        raise ApplyError("current manuscript bytes did not survive provenance restamp")


def _patch_source_eyecatch() -> None:
    page = repair._source_preflight()
    props = page.get("properties") or {}
    current = ready_sync._files_url(props.get("アイキャッチ"))
    eyecatch_contract.require_current_asset_url(IMAGE_URL, repair.NEW_TITLE)
    if current == IMAGE_URL:
        return
    payload = {
        "properties": {
            "アイキャッチ": {
                "files": [{
                    "name": Path(IMAGE_URL).name,
                    "type": "external",
                    "external": {"url": IMAGE_URL},
                }]
            }
        }
    }
    response = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{repair.SYNC_ID}",
        json=payload,
    )
    if response.status_code != 200:
        raise ApplyError(f"Notion eyecatch-only update failed: HTTP {response.status_code}")
    page = repair._source_preflight()
    updated = ready_sync._files_url((page.get("properties") or {}).get("アイキャッチ"))
    if updated != IMAGE_URL:
        raise ApplyError("Notion eyecatch URL did not persist")


def _backup_current_cover(page: Any) -> str:
    existing = official_image._find_existing_cover(page)
    if existing is None:
        return ""
    cover, _ = existing
    src = str(cover.evaluate("el => el.currentSrc || el.src || ''") or "")
    if not src.startswith("https://"):
        raise ApplyError("existing note cover is not downloadable HTTPS")
    response = page.request.get(src, timeout=30000)
    if not response.ok:
        raise ApplyError(f"existing note cover backup failed: HTTP {response.status}")
    body = response.body()
    if len(body) < 1024:
        raise ApplyError("existing note cover backup is unexpectedly small")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_bytes(body)
    return src


def _restore_backup(page: Any, title: str, body_manuscript: str) -> bool:
    if not BACKUP.is_file():
        return False
    try:
        official_image._upload_header_image(page, BACKUP)
        note_base._save_draft_and_verify(page, title, body_manuscript, image_required=True)
        return True
    except Exception:
        return False


def _apply_to_existing_draft(image_path: Path) -> dict[str, Any]:
    manuscript = repair.load_manuscript()
    body_manuscript = note_base._body_manuscript_for_note(repair.NEW_TITLE, manuscript)
    run190.install()
    official_image.install()
    profile = run190._profile_dir()

    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        changed_started = False
        try:
            url = repair._open_exact_draft(page, profile)
            if repair.audit_base._title_value(page) != repair.NEW_TITLE:
                raise ApplyError("unexpected VT Code draft title before eyecatch-only apply")

            title_locator = note_base._find_title(page)
            body = note_base._find_body(page, title_locator)
            note_base._verify_body_content(body, body_manuscript)

            old_identity = repair._header_media_identity(page)
            _backup_current_cover(page)

            changed_started = True
            official_image._upload_header_image(
                page,
                image_path,
                media_changed=lambda: repair._cover_changed(page, old_identity),
            )

            saved = note_base._save_draft_and_verify(
                page, repair.NEW_TITLE, body_manuscript, image_required=True
            )
            if not repair._same_edit_route(url, saved):
                raise ApplyError("eyecatch-only apply escaped the existing private draft")

            new_identity = repair._header_media_identity(page)
            if new_identity == old_identity:
                raise ApplyError("production eyecatch did not replace the previous cover")

            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)

            if repair.audit_base._title_value(page) != repair.NEW_TITLE:
                raise ApplyError("title changed after eyecatch-only apply")
            body = note_base._find_body(page, note_base._find_title(page))
            note_base._verify_body_content(body, body_manuscript)

            persisted_identity = repair._header_media_identity(page)
            if persisted_identity != new_identity:
                raise ApplyError("production eyecatch did not persist after reload")

            metrics = eyecatch.collect_eyecatch_metrics(
                page, title_locator=note_base._find_title(page)
            )
            if not eyecatch.eyecatch_persistence_confirmed(metrics):
                raise ApplyError("shared eyecatch persistence proof failed")

            return {
                "status": "vtcode_current_eyecatch_applied",
                "same_edit_route": True,
                "title_unchanged": True,
                "body_unchanged": True,
                "eyecatch_identity_changed": True,
                "persisted_after_reload": True,
                "new_draft_created": False,
                "public_release": False,
                "editor_route_hash": hashlib.sha256(repair._route_key(url).encode()).hexdigest()[:12],
            }
        except Exception:
            if changed_started:
                _restore_backup(page, repair.NEW_TITLE, body_manuscript)
            raise
        finally:
            context.close()


def main() -> None:
    eyecatch_contract.require_current_asset_url(IMAGE_URL, repair.NEW_TITLE)
    image_path = note_base._download_eyecatch(IMAGE_URL, repair.SYNC_ID, repair.NEW_TITLE)
    try:
        _patch_source_eyecatch()
        _restamp_current_manuscript_bytes()
        # Keep the posting row's quality contract synchronized after current asset/provenance updates.
        ready_sync.sync_note_ready_db(target_sync_id=repair.SYNC_ID)
        state = repair.destination_preflight()
        result = _apply_to_existing_draft(image_path)
        result.update({
            "current_asset_url": True,
            "notion_source_eyecatch_updated": True,
            "quality_state_preserved": state["quality_state"],
            "posting_state_preserved": state["posting_state"],
            "zero_gemini_calls": True,
        })
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    finally:
        image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
