#!/usr/bin/env python3
"""Run193 overlay: upload note eyecatches through the visible official header-image UI.

Live Run192 screenshot evidence showed that the previous drag/drop path never opened note's
crop UI. The only role=dialog on screen was the unrelated note AI assistant toast (with only a
"閉じる" control), while the real circular header-image button was visibly present above the
title. Current note help also documents the normal PC flow as header image icon ->
"画像をアップロード" -> choose file.

Safety contract:
- zero Gemini/model calls;
- no public-release/post action;
- use the normal visible note editor UI, not a private/internal posting API;
- identify the header icon only above/near the proven title field;
- ignore unrelated dialogs such as the AI assistant toast;
- fail closed on ambiguous header controls, upload controls, or crop completion controls.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run188_note_header_upload_fallback as run188
import run189_note_editor_route_gate as run189
import run191_note_crop_dialog_resilience as run191

_REJECT_CONTROL_TERMS = ("公開", "投稿", "下書き", "保存", "閉じる", "キャンセル", "削除", "publish", "post", "save draft", "close", "cancel", "delete")
_CROP_POSITIVE_TERMS = ("保存", "完了", "決定", "適用", "確定", "使用", "反映", "挿入", "save", "done", "apply", "confirm", "use image", "insert")
_CROP_REJECT_TERMS = ("公開", "投稿", "キャンセル", "閉じる", "削除", "戻る", "publish", "post", "cancel", "close", "delete", "back")


def _semantic_text(control: Any) -> str:
    parts: list[str] = []
    for getter in (
        lambda: control.inner_text(timeout=250),
        lambda: control.get_attribute("aria-label"),
        lambda: control.get_attribute("title"),
        lambda: control.get_attribute("data-testid"),
        lambda: control.get_attribute("name"),
    ):
        try:
            value = getter()
        except Exception:
            value = None
        if value:
            parts.append(str(value).strip())
    return " ".join(parts).strip().lower()


def _header_button_score(meta: dict[str, Any], title_box: dict[str, float]) -> float | None:
    try:
        x = float(meta["x"]); y = float(meta["y"]); width = float(meta["width"]); height = float(meta["height"])
        title_x = float(title_box["x"]); title_y = float(title_box["y"]); title_w = float(title_box.get("width", 700.0))
    except (KeyError, TypeError, ValueError):
        return None
    if width < 22 or width > 82 or height < 22 or height > 82:
        return None
    cx, cy = x + width / 2.0, y + height / 2.0
    vertical_gap = title_y - cy
    if vertical_gap < 35 or vertical_gap > 190:
        return None
    if cx < title_x - 70 or cx > title_x + min(240.0, max(120.0, title_w * 0.45)):
        return None
    semantic = str(meta.get("semantic") or "").lower()
    if any(term in semantic for term in _REJECT_CONTROL_TERMS):
        return None
    if not bool(meta.get("has_graphic")) and not any(term in semantic for term in ("画像", "image", "cover", "見出し")):
        return None
    return abs(cx - (title_x + 20.0)) + abs(cy - (title_y - 100.0))


def _find_header_add_control(page: Any) -> Any:
    explicit = base._first_visible(page, [
        'button[aria-label*="見出し画像"]', '[role="button"][aria-label*="見出し画像"]',
        'button[title*="見出し画像"]', '[role="button"][title*="見出し画像"]', 'button[aria-label="画像を追加"]',
    ], timeout_ms=900)
    if explicit is not None:
        return explicit
    title = base._find_title(page)
    try:
        title_box = title.bounding_box()
    except Exception:
        title_box = None
    if not title_box:
        raise base.NoteDraftError("note header image icon could not be anchored to the title field")
    controls = page.locator('button, [role="button"]')
    ranked: list[tuple[float, int, Any]] = []
    try:
        count = min(controls.count(), 120)
    except Exception:
        count = 0
    for index in range(count):
        control = controls.nth(index)
        try:
            if not control.is_visible(timeout=120):
                continue
            box = control.bounding_box()
            if not box:
                continue
            meta = {**box, "semantic": _semantic_text(control), "has_graphic": bool(control.locator("svg, img").count())}
        except Exception:
            continue
        score = _header_button_score(meta, title_box)
        if score is not None:
            ranked.append((score, index, control))
    if not ranked:
        raise base.NoteDraftError("note official header-image icon was not found above the title")
    ranked.sort(key=lambda row: (row[0], row[1]))
    if len(ranked) > 1 and abs(ranked[1][0] - ranked[0][0]) < 12:
        raise base.NoteDraftError("note header-image icon geometry was ambiguous; refusing to click")
    return ranked[0][2]


def _find_upload_menu_control(page: Any) -> Any:
    control = base._first_visible(page, [
        'button:has-text("画像をアップロード")', '[role="button"]:has-text("画像をアップロード")',
        '[role="menuitem"]:has-text("画像をアップロード")', 'text="画像をアップロード"',
    ], timeout_ms=5000)
    if control is None:
        raise base.NoteDraftError("note header-image menu did not expose 画像をアップロード")
    semantic = _semantic_text(control)
    if any(term in semantic for term in ("公開", "投稿", "削除", "publish", "post", "delete")):
        raise base.NoteDraftError("unsafe note control matched the header upload menu")
    return control


def _set_file_from_official_menu(page: Any, upload_control: Any, image_path: Path) -> None:
    try:
        with page.expect_file_chooser(timeout=6000) as chooser_info:
            upload_control.click()
        chooser_info.value.set_files(str(image_path))
        return
    except Exception:
        pass
    inputs = page.locator('input[type="file"]')
    candidates: list[Any] = []
    try:
        count = min(inputs.count(), 12)
    except Exception:
        count = 0
    for index in range(count):
        item = inputs.nth(index)
        try:
            accept = str(item.get_attribute("accept") or "").lower()
        except Exception:
            accept = ""
        if accept and "image" not in accept and not any(ext in accept for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic")):
            continue
        candidates.append(item)
    if len(candidates) != 1:
        raise base.NoteDraftError("note header upload did not expose one unambiguous image file input")
    try:
        candidates[0].set_input_files(str(image_path))
    except Exception as exc:
        raise base.NoteDraftError("note official header image file input rejected the eyecatch") from exc


def _visible_modal_roots(page: Any) -> list[Any]:
    roots: list[Any] = []
    locator = page.locator('[role="dialog"], [aria-modal="true"]')
    try:
        count = min(locator.count(), 20)
    except Exception:
        count = 0
    for index in range(count):
        root = locator.nth(index)
        try:
            if root.is_visible(timeout=150):
                roots.append(root)
        except Exception:
            continue
    return roots


def _safe_crop_candidates(root: Any) -> list[Any]:
    result: list[Any] = []
    controls = root.locator('button, [role="button"]')
    try:
        count = min(controls.count(), 40)
    except Exception:
        count = 0
    for index in range(count):
        control = controls.nth(index)
        try:
            if not control.is_visible(timeout=120) or not control.is_enabled():
                continue
        except Exception:
            continue
        semantic = _semantic_text(control)
        if not semantic or any(term in semantic for term in _CROP_REJECT_TERMS):
            continue
        if any(term in semantic for term in _CROP_POSITIVE_TERMS):
            result.append(control)
    return result


def _root_looks_crop_related(root: Any) -> bool:
    try:
        if root.locator('canvas, input[type="range"], img').count() > 0:
            return True
    except Exception:
        pass
    try:
        text = str(root.inner_text(timeout=250) or "").lower()
    except Exception:
        text = ""
    if any(term in text for term in ("トリミング", "切り抜", "画像", "拡大", "縮小", "crop", "zoom")):
        return True
    return bool(_safe_crop_candidates(root))


def _post_upload_diagnostics(page: Any) -> str:
    try:
        roots = _visible_modal_roots(page); crop_like = sum(1 for root in roots if _root_looks_crop_related(root))
    except Exception:
        roots, crop_like = [], -1
    try:
        images = min(page.locator("img").count(), 99)
    except Exception:
        images = -1
    return f"visible_modals={len(roots)}; crop_like_modals={crop_like}; images={images}"


def _finish_real_crop_or_preview(page: Any) -> None:
    deadline = time.time() + 22.0
    while time.time() < deadline:
        if run188._header_preview_present(page):
            return
        crop_roots = [root for root in _visible_modal_roots(page) if _root_looks_crop_related(root)]
        candidates: list[tuple[int, Any, Any]] = []
        for root_index, root in enumerate(crop_roots):
            for control in _safe_crop_candidates(root):
                candidates.append((root_index, root, control))
        if candidates:
            if len(candidates) != 1:
                raise base.NoteDraftError("note crop UI exposed multiple safe completion controls; " + _post_upload_diagnostics(page))
            _, root, control = candidates[0]
            try:
                control.click()
                try:
                    root.wait_for(state="hidden", timeout=15000)
                except Exception:
                    pass
            except Exception as exc:
                raise base.NoteDraftError("note official crop completion click failed") from exc
        page.wait_for_timeout(350)
    raise base.NoteDraftError("note official header upload produced neither a verified header preview nor a completable crop UI; " + _post_upload_diagnostics(page))


def _upload_header_image(page: Any, image_path: Path) -> None:
    run189._ensure_editor_route(page)
    add_control = _find_header_add_control(page)
    try:
        add_control.click()
    except Exception as exc:
        raise base.NoteDraftError("note official header-image icon could not be clicked") from exc
    upload_control = _find_upload_menu_control(page)
    _set_file_from_official_menu(page, upload_control, image_path)
    _finish_real_crop_or_preview(page)


def install() -> None:
    run191.install()
    base._upload_header_image = _upload_header_image


def main() -> None:
    install()
    run189.run185.main()


if __name__ == "__main__":
    main()
