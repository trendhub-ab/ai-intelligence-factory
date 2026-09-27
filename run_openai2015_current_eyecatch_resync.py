#!/usr/bin/env python3
"""Repair OpenAI (2015) eyecatch contract and resync the existing private note draft.

One-off safety contract:
- exact Content Intelligence page and exact existing private draft only;
- zero Gemini/model calls;
- render with current deterministic AIIF eyecatch layers;
- upload image + manifest to runtime-state under the current eyecatch contract;
- recaption the exact operator-approved manuscript under the current publication policy;
- update the existing note edit route only; never create or publicly release a draft.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image
import eyecatch_publication_contract as eyecatch_contract
import note_draft_automation as note_base
import note_eyecatch_persistence as eyecatch_persistence
import note_ready_sync as ready_sync
import pipeline
import publication_contract
import run181_eyecatch_visual_balance as run181
import run183_eyecatch_emphasis_scale as run183
import run190_note_persistent_cloud as run190
import run193_note_official_header_upload as official_image
import run417_note_body_verification as run417
import run_openai2015_existing_draft_resync as repair
from notion_payloads import build_notion_manuscript_children
from run_sgps_existing_draft_repair import _route_key, _same_edit_route

CONFIRM_TOKEN = "REPAIR_OPENAI2015_CURRENT_EYECATCH_RESYNC"
OUTPUT = Path(".runtime/openai2015-current-eyecatch.png")
ASSET_BASE = "OpenAI_2015.png"
ASSET_BRANCH = "runtime-state"
SUMMARY = (
    "2015年12月11日、OpenAIが非営利のAI研究企業として設立を発表し、"
    "人類全体への利益を優先する目的、研究成果の公開、特許共有、幅広い協力方針を掲げた一次資料です。"
)
EYECATCH_TITLE = "OpenAIは非営利から始まった。2015年の原点を読み直す"
TITLE_LINES = ["OpenAIは非営利から始まった", "2015年の原点を読み直す"]
SUBHEAD_LINES = ["設立時に何を掲げたのか。", "2015年の公式発表を読み直す。"]
HIGHLIGHT = "2015年の原点を読み直す"
CATEGORY = "AI BUSINESS"


class RepairError(RuntimeError):
    pass


def render_current_eyecatch() -> Path:
    run183.install(pipeline)
    plan = {
        "eyecatch_title": EYECATCH_TITLE,
        "title_lines": TITLE_LINES,
        "title_font_size": 68,
        "title_line_gap": 12,
        "subheadline_lines": SUBHEAD_LINES,
        "subheadline_font_size": 24,
        "highlight_text": HIGHLIGHT,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    run181._render_balanced_plan(
        repair.TITLE,
        SUMMARY,
        str(OUTPUT),
        plan,
        category=CATEGORY,
        date_label="2026.09",
        highlight_text=HIGHLIGHT,
    )
    with Image.open(OUTPUT) as image:
        if image.size != (1280, 670):
            raise RepairError(f"eyecatch size mismatch: {image.size}")
    return OUTPUT


def upload_current_eyecatch(image_path: Path) -> str:
    pipeline.EYECATCH_GITHUB_BRANCH = ASSET_BRANCH
    image_url = eyecatch_contract.upload_current_asset_pair(
        pipeline.upload_eyecatch_to_github,
        image_path,
        ASSET_BASE,
        repair.TITLE,
    )
    if not image_url:
        raise RepairError("current eyecatch image/manifest upload failed")
    eyecatch_contract.require_current_asset_url(image_url, repair.TITLE)
    return image_url


def exact_chunks(text: str, limit: int = 1800) -> list[str]:
    """Split only by byte-preserving character slices; concatenation must equal input."""
    value = str(text or "")
    if limit <= 0:
        raise ValueError("chunk limit must be positive")
    chunks = [value[i:i + limit] for i in range(0, len(value), limit)]
    if "".join(chunks) != value:
        raise RepairError("exact manuscript chunking changed persisted bytes")
    return chunks


def ensure_current_manuscript(manuscript: str) -> None:
    current = ready_sync._source_current_ready_manuscript(repair.SYNC_ID)
    if current == manuscript:
        return
    caption = publication_contract.current_ready_caption(manuscript)
    if not publication_contract.is_current_ready_block(manuscript, caption):
        raise RepairError("current manuscript caption self-check failed")
    children = build_notion_manuscript_children(
        manuscript,
        caption,
        chunker=lambda text: exact_chunks(text, 1800),
    )
    response = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{repair.SYNC_ID}/children",
        json={"children": children},
    )
    if response.status_code != 200:
        raise RepairError(f"current manuscript append failed: HTTP {response.status_code}")
    if ready_sync._source_current_ready_manuscript(repair.SYNC_ID) != manuscript:
        raise RepairError("current manuscript did not survive byte verification")


def patch_source_eyecatch(image_url: str) -> None:
    page = repair._source_page()
    props = page.get("properties") or {}
    current = ready_sync._files_url(props.get("アイキャッチ"))
    if current == image_url:
        return
    response = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{repair.SYNC_ID}",
        json={
            "properties": {
                "アイキャッチ": {
                    "files": [
                        {
                            "name": Path(image_url).name,
                            "type": "external",
                            "external": {"url": image_url},
                        }
                    ]
                }
            }
        },
    )
    if response.status_code != 200:
        raise RepairError(f"Notion eyecatch update failed: HTTP {response.status_code}")
    updated = repair._source_page()
    updated_url = ready_sync._files_url((updated.get("properties") or {}).get("アイキャッチ"))
    if updated_url != image_url:
        raise RepairError("Notion eyecatch URL did not persist")


def header_media_identity(page: Any) -> str:
    title_box = note_base._find_title(page).bounding_box()
    if not title_box:
        raise RepairError("draft title has no geometry for cover verification")
    media = page.evaluate(
        """(titleY) => {
            const result = [];
            for (const el of document.querySelectorAll('img, picture, figure, section, div')) {
                const r = el.getBoundingClientRect();
                if (r.width < 420 || r.height < 140 || r.top >= titleY || r.top < -500) continue;
                const style = getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') continue;
                const value = el.tagName === 'IMG' ? (el.currentSrc || el.src) :
                    (style.backgroundImage !== 'none' ? style.backgroundImage : '');
                if (value) result.push(value);
            }
            return [...new Set(result)];
        }""",
        float(title_box["y"]),
    )
    if not isinstance(media, list) or len(media) != 1:
        raise RepairError("cover media cannot be identified uniquely")
    return hashlib.sha256(str(media[0]).encode("utf-8")).hexdigest()


def cover_changed(page: Any, old_identity: str) -> bool:
    try:
        return header_media_identity(page) != old_identity
    except RepairError:
        return False


def browser_resync(manuscript: str, image_path: Path, *, expected_route: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    body_manuscript = note_base._body_manuscript_for_note(repair.TITLE, manuscript)
    run190.install()
    run417.install(note_base)
    official_image.install()
    profile = run190._profile_dir()

    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            url = repair._find_exact_existing_draft(page, profile)
            if not _same_edit_route(expected_route, url):
                raise RepairError("existing draft route changed after preflight")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            if (
                not _same_edit_route(url, str(page.url))
                or repair.audit_base._title_value(page) != repair.TITLE
            ):
                raise RepairError("exact existing note draft identity changed")

            old_cover = header_media_identity(page)
            title_field = note_base._set_title(page, repair.TITLE)
            body = note_base._find_body(page, title_field)
            note_base._paste_manuscript(page, body, body_manuscript)
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, body_manuscript)

            official_image._upload_header_image(
                page,
                image_path,
                media_changed=lambda: cover_changed(page, old_cover),
            )
            saved = note_base._save_draft_and_verify(
                page, repair.TITLE, body_manuscript, image_required=True
            )
            if not _same_edit_route(url, saved):
                raise RepairError("save escaped the existing OpenAI 2015 private draft")

            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if repair.audit_base._title_value(page) != repair.TITLE:
                raise RepairError("title changed after reload")
            body = note_base._find_body(page, note_base._find_title(page))
            note_base._verify_body_content(body, body_manuscript)

            new_cover = header_media_identity(page)
            if new_cover == old_cover:
                raise RepairError("current eyecatch did not replace the stale cover")
            metrics = eyecatch_persistence.collect_eyecatch_metrics(
                page, title_locator=note_base._find_title(page)
            )
            if not eyecatch_persistence.eyecatch_persistence_confirmed(metrics):
                raise RepairError("eyecatch persistence proof failed")

            return {
                "status": "openai2015_current_resync_completed",
                "same_edit_route": True,
                "title_match": True,
                "body_verified": True,
                "eyecatch_replaced": True,
                "persisted_after_reload": True,
                "new_draft_created": False,
                "public_release": False,
                "zero_gemini_calls": True,
                "editor_route_hash": hashlib.sha256(_route_key(url).encode("utf-8")).hexdigest()[:12],
            }
        finally:
            context.close()


def run(*, confirm: str, prepare_only: bool = False) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise RepairError("exact repair confirmation token is required")

    repair._source_page()
    manuscript = repair._operator_manuscript()
    state = repair._destination_page(require_ready=False)
    result: dict[str, Any] = {
        "status": "repair_ready" if prepare_only else "openai2015_current_resync_completed",
        "sync_id": repair.SYNC_ID,
        "zero_gemini_calls": True,
        "new_draft_created": False,
        "public_release": False,
        "posting_state_preserved": state["posting_state"],
        "eyecatch_title": EYECATCH_TITLE,
        "badge": "原点を知る",
    }
    if prepare_only:
        return result

    route = repair._draft_route_preflight()
    image_path = render_current_eyecatch()
    try:
        image_url = upload_current_eyecatch(image_path)
        ensure_current_manuscript(manuscript)
        patch_source_eyecatch(image_url)
        ready_sync.sync_note_ready_db(target_sync_id=repair.SYNC_ID)
        state = repair._destination_page(require_ready=True)
        result.update(browser_resync(manuscript, image_path, expected_route=route))
        result.update(
            {
                "current_asset_url": True,
                "notion_source_eyecatch_updated": True,
                "quality_state_after_sync": state["quality_state"],
                "posting_state_after_sync": state["posting_state"],
            }
        )
        return result
    finally:
        image_path.unlink(missing_ok=True)


def main() -> None:
    import os

    result = run(
        confirm=os.environ.get("OPENAI2015_CURRENT_RESYNC_CONFIRM", ""),
        prepare_only=os.environ.get("OPENAI2015_CURRENT_RESYNC_PREPARE_ONLY", "").lower()
        in {"1", "true", "yes", "on"},
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
