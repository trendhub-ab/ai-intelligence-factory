#!/usr/bin/env python3
"""Run186 overlay: resilient note header-image handling for the normal web editor.

The note editor changes accessible labels over time and may reveal the header-image control
only after the header area is hovered. This overlay keeps the existing fail-closed draft
contract while broadening only the header-image interaction surface.

Safety:
- zero Gemini/model calls;
- no public-release action;
- never falls back to a generic body-image toolbar button below the title;
- verifies a persisted large image above the title after the draft is reopened.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run185_note_ready_legacy_skip as run185


_ORIGINAL_SAVE_DRAFT_AND_VERIFY = base._save_draft_and_verify

_EXPLICIT_HEADER_IMAGE_RE = re.compile(
    r"(?:見出し画像|アイキャッチ|ヘッダー画像|カバー画像|画像を追加|画像を設定|画像を変更)",
    re.I,
)
_IMAGE_WORD_RE = re.compile(r"画像|写真", re.I)


def _control_label(locator: Any) -> str:
    parts: list[str] = []
    for attr in ("aria-label", "title", "data-testid"):
        try:
            value = locator.get_attribute(attr)
        except Exception:
            value = None
        if value:
            parts.append(str(value))
    try:
        text = str(locator.inner_text(timeout=400) or "").strip()
    except Exception:
        text = ""
    if text:
        parts.append(text)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _header_label_score(label: str) -> int | None:
    normalized = re.sub(r"\s+", "", str(label or ""))
    if not normalized:
        return None
    if _EXPLICIT_HEADER_IMAGE_RE.search(normalized):
        return 0
    if normalized in {"画像", "写真"}:
        return 2
    if _IMAGE_WORD_RE.search(normalized) and any(token in normalized for token in ("追加", "設定", "変更")):
        return 1
    return None


def _candidate_header_control(page: Any) -> Any | None:
    """Return a visible image control located in the header zone, never below the title."""
    title = base._find_title(page)
    try:
        title_box = title.bounding_box()
    except Exception:
        title_box = None
    if not title_box:
        return None
    title_y = float(title_box.get("y", 999999))
    title_x = float(title_box.get("x", 0))
    title_w = float(title_box.get("width", 900))

    selectors = (
        'button[aria-label*="画像"], [role="button"][aria-label*="画像"], '
        'button[aria-label*="写真"], [role="button"][aria-label*="写真"], '
        'button[title*="画像"], [role="button"][title*="画像"], '
        'button[title*="写真"], [role="button"][title*="写真"], '
        'button:has-text("画像を追加"), [role="button"]:has-text("画像を追加"), '
        'button:has-text("見出し画像"), [role="button"]:has-text("見出し画像"), '
        'button:has-text("アイキャッチ"), [role="button"]:has-text("アイキャッチ")'
    )

    try:
        page.mouse.move(title_x + max(20.0, title_w / 2), max(20.0, title_y - 42.0))
        page.wait_for_timeout(500)
    except Exception:
        pass

    locator = page.locator(selectors)
    ranked: list[tuple[int, float, Any]] = []
    try:
        count = min(locator.count(), 40)
    except Exception:
        count = 0
    for index in range(count):
        item = locator.nth(index)
        try:
            if not item.is_visible(timeout=500):
                continue
            box = item.bounding_box()
            if not box:
                continue
            y = float(box.get("y", 999999))
            if y > title_y + 12:
                continue
            score = _header_label_score(_control_label(item))
            if score is None:
                continue
            ranked.append((score, abs(title_y - y), item))
        except Exception:
            continue
    if not ranked:
        return None
    ranked.sort(key=lambda row: (row[0], row[1]))
    return ranked[0][2]


def _image_file_input(page: Any) -> Any | None:
    candidates = page.locator('input[type="file"]')
    usable: list[Any] = []
    try:
        count = min(candidates.count(), 12)
    except Exception:
        count = 0
    for index in range(count):
        item = candidates.nth(index)
        try:
            accept = str(item.get_attribute("accept") or "").lower()
        except Exception:
            accept = ""
        if accept and "image" not in accept and not any(ext in accept for ext in (".png", ".jpg", ".jpeg", ".webp")):
            continue
        usable.append(item)
    return usable[0] if len(usable) == 1 else None


def _upload_header_image(page: Any, image_path: Path) -> None:
    deadline = time.time() + 12
    add_button = None
    while time.time() < deadline and add_button is None:
        add_button = _candidate_header_control(page)
        if add_button is None:
            page.wait_for_timeout(600)
    if add_button is None:
        raise base.NoteDraftError("note header-image control was not found after header hover/retry")

    try:
        add_button.click()
    except Exception as exc:
        raise base.NoteDraftError("note header-image control could not be clicked") from exc
    page.wait_for_timeout(500)

    upload_button = base._first_visible(
        page,
        [
            'button:has-text("画像をアップロード")',
            '[role="button"]:has-text("画像をアップロード")',
            'button:has-text("アップロード")',
            '[role="button"]:has-text("アップロード")',
            'button:has-text("ファイルを選択")',
            '[role="button"]:has-text("ファイルを選択")',
        ],
        timeout_ms=5000,
    )

    chooser_used = False
    if upload_button is not None:
        try:
            with page.expect_file_chooser(timeout=5000) as chooser_info:
                upload_button.click()
            chooser_info.value.set_files(str(image_path))
            chooser_used = True
        except Exception:
            chooser_used = False

    if not chooser_used:
        file_input = _image_file_input(page)
        if file_input is None:
            raise base.NoteDraftError("note eyecatch file chooser was not available or was ambiguous")
        try:
            file_input.set_input_files(str(image_path))
        except Exception as exc:
            raise base.NoteDraftError("note eyecatch file chooser could not accept the image") from exc

    page.wait_for_timeout(1200)
    dialog = page.locator('[role="dialog"]').first
    try:
        dialog_visible = dialog.is_visible(timeout=2500)
    except Exception:
        dialog_visible = False
    if dialog_visible:
        save_button = base._first_visible(
            dialog,
            [
                'button:has-text("保存")',
                '[role="button"]:has-text("保存")',
                'button:has-text("完了")',
                '[role="button"]:has-text("完了")',
            ],
            timeout_ms=5000,
        )
        if save_button is None:
            raise base.NoteDraftError("note eyecatch crop dialog has no save/complete control")
        try:
            deadline = time.time() + 20
            while time.time() < deadline and not save_button.is_enabled():
                page.wait_for_timeout(300)
            if not save_button.is_enabled():
                raise base.NoteDraftError("note eyecatch crop dialog never became saveable")
            save_button.click()
            dialog.wait_for(state="hidden", timeout=15000)
        except base.NoteDraftError:
            raise
        except Exception as exc:
            raise base.NoteDraftError("note eyecatch crop/save step failed") from exc

    error_locator = page.locator('text=/アップロード.*(失敗|できません|エラー)/').first
    try:
        if error_locator.is_visible(timeout=800):
            raise base.NoteDraftError("note reported an eyecatch upload error")
    except base.NoteDraftError:
        raise
    except Exception:
        pass


def _persisted_header_image(page: Any) -> bool:
    title = base._find_title(page)
    try:
        title_box = title.bounding_box()
    except Exception:
        title_box = None
    if not title_box:
        return False
    title_y = float(title_box.get("y", 999999))

    semantic = page.locator(
        'button[aria-label*="画像を変更"], [role="button"][aria-label*="画像を変更"], '
        'button[aria-label*="見出し画像"], [role="button"][aria-label*="見出し画像"], '
        'button[aria-label*="アイキャッチ"], [role="button"][aria-label*="アイキャッチ"], '
        'button[title*="画像を変更"], [role="button"][title*="画像を変更"]'
    )
    try:
        count = min(semantic.count(), 20)
    except Exception:
        count = 0
    for index in range(count):
        item = semantic.nth(index)
        try:
            if not item.is_visible(timeout=400):
                continue
            box = item.bounding_box()
            if box and float(box.get("y", 999999)) <= title_y + 12:
                return True
        except Exception:
            continue

    images = page.locator("img")
    try:
        count = min(images.count(), 60)
    except Exception:
        count = 0
    for index in range(count):
        image = images.nth(index)
        try:
            if not image.is_visible(timeout=300):
                continue
            box = image.bounding_box()
            if not box:
                continue
            y = float(box.get("y", 999999))
            width = float(box.get("width", 0))
            height = float(box.get("height", 0))
            if y < title_y and width >= 480 and height >= 120:
                return True
        except Exception:
            continue
    return False


def _save_draft_and_verify(page: Any, title: str, manuscript: str, image_required: bool = True) -> str:
    draft_url = _ORIGINAL_SAVE_DRAFT_AND_VERIFY(page, title, manuscript, image_required=False)
    if image_required and not _persisted_header_image(page):
        raise base.NoteDraftError("note eyecatch persistence verification failed")
    return draft_url


def install() -> None:
    base._upload_header_image = _upload_header_image
    base._save_draft_and_verify = _save_draft_and_verify


def main() -> None:
    install()
    run185.main()


if __name__ == "__main__":
    main()
