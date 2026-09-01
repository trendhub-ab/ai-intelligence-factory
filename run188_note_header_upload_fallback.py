#!/usr/bin/env python3
"""Run188 overlay: upload note header image without depending on a visible header button.

Live Run186/187 proved the authenticated editor and title field can be reached, but the
current note editor does not always expose an accessible header-image button. This overlay
uses two narrowly scoped, fail-closed fallbacks before any title/body content is written:

1. Reuse a uniquely identifiable image file input that belongs to the header zone.
2. If no safe input exists, use note's supported drag-and-drop header interaction above
   the title. The drop is constrained geometrically to the header zone.

Safety:
- zero Gemini/model calls;
- no public-release action;
- never clicks or opens the body image toolbar;
- never chooses among ambiguous file inputs;
- verifies that a large image/cover surface exists above the title before continuing;
- diagnostics expose only DOM counts/location, never article text, cookies, or URLs with
  query parameters.
"""
from __future__ import annotations

import base64
import mimetypes
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as base
import run185_note_ready_legacy_skip as run185
import run186_note_header_image_resilience as run186
import run187_note_editor_readiness as run187


_HEADER_WORD_RE = re.compile(r"見出し|アイキャッチ|ヘッダー|カバー|header|cover|eyecatch", re.I)
_IMAGE_WORD_RE = re.compile(r"画像|写真|image|photo|picture", re.I)


def _mime_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and guessed.startswith("image/"):
        return guessed
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".heic": "image/heic",
    }.get(suffix, "image/png")


def _header_input_score(meta: dict[str, Any], total_image_inputs: int) -> int | None:
    """Return a lower-is-better safety score, or None when the input is ambiguous."""
    accept = str(meta.get("accept") or "").lower()
    if accept and "image" not in accept and not any(
        ext in accept for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic")
    ):
        return None

    semantic = str(meta.get("semantic") or "")
    if _HEADER_WORD_RE.search(semantic):
        return 0
    if _IMAGE_WORD_RE.search(semantic) and bool(meta.get("ancestor_above_title")):
        return 1
    if bool(meta.get("ancestor_above_title")):
        return 2
    # Before the body image toolbar is opened, exactly one image-capable file input is a
    # sufficiently narrow fallback. Multiple unlabelled inputs stay fail-closed.
    if total_image_inputs == 1:
        return 3
    return None


def _input_metadata(item: Any, title_y: float) -> dict[str, Any]:
    try:
        data = item.evaluate(
            """el => {
                const attrs = ['id','name','aria-label','title','data-testid','data-role','accept'];
                const parts = [];
                for (const key of attrs) {
                    const value = el.getAttribute(key);
                    if (value) parts.push(value);
                }
                if (el.labels) {
                    for (const label of Array.from(el.labels)) {
                        const aria = label.getAttribute('aria-label');
                        const title = label.getAttribute('title');
                        if (aria) parts.push(aria);
                        if (title) parts.push(title);
                        const text = (label.textContent || '').trim();
                        if (text && text.length <= 80) parts.push(text);
                    }
                }
                let ancestor = el.parentElement;
                let rect = null;
                for (let i = 0; ancestor && i < 7; i += 1, ancestor = ancestor.parentElement) {
                    const r = ancestor.getBoundingClientRect();
                    const aria = ancestor.getAttribute('aria-label');
                    const title = ancestor.getAttribute('title');
                    const testid = ancestor.getAttribute('data-testid');
                    if (aria) parts.push(aria);
                    if (title) parts.push(title);
                    if (testid) parts.push(testid);
                    if (!rect && r.width >= 20 && r.height >= 20) {
                        rect = {y: r.y, width: r.width, height: r.height};
                    }
                }
                return {
                    accept: el.getAttribute('accept') || '',
                    semantic: parts.join(' ').slice(0, 500),
                    ancestor: rect,
                };
            }"""
        )
    except Exception:
        data = {}
    ancestor = data.get("ancestor") if isinstance(data, dict) else None
    ancestor_y = None
    if isinstance(ancestor, dict):
        try:
            ancestor_y = float(ancestor.get("y"))
        except (TypeError, ValueError):
            ancestor_y = None
    semantic = str((data or {}).get("semantic") or "") if isinstance(data, dict) else ""
    accept = str((data or {}).get("accept") or "") if isinstance(data, dict) else ""
    return {
        "accept": accept,
        "semantic": semantic,
        "ancestor_above_title": ancestor_y is not None and ancestor_y <= title_y + 16,
    }


def _safe_header_file_input(page: Any) -> tuple[Any | None, int]:
    title = base._find_title(page)
    try:
        title_box = title.bounding_box()
    except Exception:
        title_box = None
    if not title_box:
        return None, 0
    title_y = float(title_box.get("y", 999999))

    locator = page.locator('input[type="file"]')
    candidates: list[tuple[Any, dict[str, Any]]] = []
    try:
        count = min(locator.count(), 20)
    except Exception:
        count = 0
    for index in range(count):
        item = locator.nth(index)
        meta = _input_metadata(item, title_y)
        accept = str(meta.get("accept") or "").lower()
        if accept and "image" not in accept and not any(
            ext in accept for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic")
        ):
            continue
        candidates.append((item, meta))

    total = len(candidates)
    ranked: list[tuple[int, int, Any]] = []
    for index, (item, meta) in enumerate(candidates):
        score = _header_input_score(meta, total)
        if score is not None:
            ranked.append((score, index, item))
    if not ranked:
        return None, total
    ranked.sort(key=lambda row: (row[0], row[1]))
    best_score = ranked[0][0]
    if sum(1 for row in ranked if row[0] == best_score) != 1:
        return None, total
    return ranked[0][2], total


def _finish_crop_dialog(page: Any) -> None:
    dialog = page.locator('[role="dialog"]').first
    try:
        visible = dialog.is_visible(timeout=1800)
    except Exception:
        visible = False
    if not visible:
        return

    save = base._first_visible(
        dialog,
        [
            'button:has-text("保存")',
            '[role="button"]:has-text("保存")',
            'button:has-text("完了")',
            '[role="button"]:has-text("完了")',
            'button:has-text("決定")',
            '[role="button"]:has-text("決定")',
            'button:has-text("適用")',
            '[role="button"]:has-text("適用")',
        ],
        timeout_ms=4500,
    )
    if save is None:
        raise base.NoteDraftError("note eyecatch crop dialog has no safe save/complete control")
    try:
        deadline = time.time() + 20
        while time.time() < deadline and not save.is_enabled():
            page.wait_for_timeout(250)
        if not save.is_enabled():
            raise base.NoteDraftError("note eyecatch crop dialog never became saveable")
        save.click()
        dialog.wait_for(state="hidden", timeout=15000)
    except base.NoteDraftError:
        raise
    except Exception as exc:
        raise base.NoteDraftError("note eyecatch crop/save step failed") from exc


def _header_preview_present(page: Any) -> bool:
    try:
        if run186._persisted_header_image(page):
            return True
    except Exception:
        pass

    title = base._find_title(page)
    try:
        title_box = title.bounding_box()
    except Exception:
        title_box = None
    if not title_box:
        return False
    title_y = float(title_box.get("y", 999999))

    # Some note builds render the cover as a CSS background rather than an <img>.
    blocks = page.locator("div, figure, picture, section")
    try:
        count = min(blocks.count(), 120)
    except Exception:
        count = 0
    for index in range(count):
        item = blocks.nth(index)
        try:
            if not item.is_visible(timeout=180):
                continue
            box = item.bounding_box()
            if not box:
                continue
            y = float(box.get("y", 999999))
            width = float(box.get("width", 0))
            height = float(box.get("height", 0))
            if y >= title_y or width < 460 or height < 100:
                continue
            background = str(item.evaluate("el => getComputedStyle(el).backgroundImage") or "")
            if background and background != "none" and "url(" in background:
                return True
        except Exception:
            continue
    return False


def _wait_for_header_preview(page: Any, seconds: float = 12.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _header_preview_present(page):
            return True
        page.wait_for_timeout(450)
    return False


def _upload_via_safe_input(page: Any, image_path: Path) -> tuple[bool, int]:
    file_input, image_input_count = _safe_header_file_input(page)
    if file_input is None:
        return False, image_input_count
    try:
        file_input.set_input_files(str(image_path))
    except Exception as exc:
        raise base.NoteDraftError("safe note header file input could not accept the eyecatch") from exc
    page.wait_for_timeout(800)
    _finish_crop_dialog(page)
    if not _wait_for_header_preview(page):
        # A file was already selected, so do not attempt another mutation path that could
        # produce a duplicate/stray image.
        raise base.NoteDraftError(
            "safe note header file input accepted a file but no header preview appeared; refusing a second upload"
        )
    return True, image_input_count


def _drop_above_title(page: Any, image_path: Path) -> bool:
    title = base._find_title(page)
    try:
        box = title.bounding_box()
    except Exception:
        box = None
    if not box:
        return False
    title_y = float(box.get("y", 0))
    title_x = float(box.get("x", 0))
    title_w = float(box.get("width", 800))
    if title_y < 70:
        return False

    # A single drop only. The target is explicitly above the title, so this cannot use
    # the body insertion zone. note's editor supports drag-and-drop for header images.
    x = max(20.0, title_x + max(20.0, title_w / 2))
    y = max(30.0, title_y - min(100.0, max(60.0, title_y * 0.22)))
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "x": x,
        "y": y,
        "name": image_path.name,
        "mime": _mime_for_path(image_path),
        "b64": encoded,
    }
    try:
        dispatched = bool(
            page.evaluate(
                """payload => {
                    const binary = atob(payload.b64);
                    const bytes = new Uint8Array(binary.length);
                    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
                    const file = new File([bytes], payload.name, {type: payload.mime});
                    const transfer = new DataTransfer();
                    transfer.items.add(file);
                    const target = document.elementFromPoint(payload.x, payload.y);
                    if (!target) return false;
                    const rect = target.getBoundingClientRect();
                    if (rect.top > payload.y + 8) return false;
                    for (const type of ['dragenter', 'dragover', 'drop']) {
                        const event = new DragEvent(type, {
                            bubbles: true,
                            cancelable: true,
                            dataTransfer: transfer,
                            clientX: payload.x,
                            clientY: payload.y,
                        });
                        target.dispatchEvent(event);
                    }
                    return true;
                }""",
                payload,
            )
        )
    except Exception:
        return False
    if not dispatched:
        return False
    page.wait_for_timeout(900)
    _finish_crop_dialog(page)
    return _wait_for_header_preview(page)


def _safe_header_diagnostics(page: Any, image_input_count: int) -> str:
    try:
        parsed = urlparse(str(page.url or ""))
        location = f"{parsed.hostname or ''}{parsed.path or '/'}"
    except Exception:
        location = "unknown"
    try:
        buttons = min(page.locator("button").count(), 99)
    except Exception:
        buttons = -1
    try:
        images = min(page.locator("img").count(), 99)
    except Exception:
        images = -1
    return f"location={location}; image_inputs={image_input_count}; buttons={buttons}; images={images}"


def _upload_header_image(page: Any, image_path: Path) -> None:
    # First prefer a directly addressable header file input. This avoids brittle visual
    # controls and works even when the visible cover button has no accessible label.
    used, image_input_count = _upload_via_safe_input(page, image_path)
    if used:
        return

    # No safe file input was identifiable. Use one geometrically constrained drop in the
    # header zone; never click the body '+' image menu as a fallback.
    if _drop_above_title(page, image_path):
        return

    raise base.NoteDraftError(
        "note header image could not be uploaded through a safe file input or header-zone drop; "
        + _safe_header_diagnostics(page, image_input_count)
    )


def install() -> None:
    # Compose prior safety overlays explicitly, then replace only the header upload step.
    run187.install()
    run186.install()
    base._upload_header_image = _upload_header_image


def main() -> None:
    install()
    run185.main()


if __name__ == "__main__":
    main()
