from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any


def find_header_image_add_button(base: Any, page: Any) -> Any | None:
    """Find the current note header-image button without guessing among multiple controls."""
    semantic = base._topmost_visible(page.locator(base._header_image_add_selector()))
    if semantic is not None:
        return semantic

    try:
        page.evaluate(
            """() => {
                window.scrollTo(0, 0);
                for (const el of document.querySelectorAll('*')) {
                    if (el.scrollTop > 0) el.scrollTop = 0;
                }
            }"""
        )
        page.wait_for_timeout(1500)
        index = page.evaluate(
            """() => {
                const bs = [...document.querySelectorAll('button')];
                const matches = bs.map((b, i) => {
                    const r = b.getBoundingClientRect();
                    const label = (b.getAttribute('aria-label') || b.innerText || '').trim();
                    const ok = !label && r.width >= 30 && r.width <= 56 &&
                        r.y > 60 && r.y < 220 && r.x > 400;
                    return ok ? i : -1;
                }).filter((i) => i >= 0);
                return matches.length === 1 ? matches[0] : -1;
            }"""
        )
    except Exception:
        return None

    if not isinstance(index, int) or index < 0:
        return None
    try:
        candidate = page.locator("button").nth(index)
        if candidate.is_visible(timeout=700):
            return candidate
    except Exception:
        pass
    return None


def upload_header_image(base: Any, page: Any, image_path: Path) -> None:
    add_button = find_header_image_add_button(base, page)
    if add_button is None:
        raise base.NoteDraftError("note header-image control was not found")
    add_button.click()

    upload_button = base._first_visible(
        page,
        ['button:has-text("画像をアップロード")', '[role="button"]:has-text("画像をアップロード")'],
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
        file_input = page.locator('input[type="file"]').first
        try:
            file_input.wait_for(state="attached", timeout=7000)
            file_input.set_input_files(str(image_path))
        except Exception as exc:
            raise base.NoteDraftError("note eyecatch file chooser was not available") from exc

    page.wait_for_timeout(1200)
    dialog = page.locator('[role="dialog"]').first
    try:
        dialog_visible = dialog.is_visible(timeout=2500)
    except Exception:
        dialog_visible = False
    if dialog_visible:
        save_button = dialog.get_by_role("button", name=re.compile(r"^保存$")).first
        try:
            save_button.wait_for(state="visible", timeout=10000)
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

    page.wait_for_timeout(1000)
    error_locator = page.locator('text=/アップロード.*(失敗|できません|エラー)/').first
    try:
        if error_locator.is_visible(timeout=800):
            raise base.NoteDraftError("note reported an eyecatch upload error")
    except base.NoteDraftError:
        raise
    except Exception:
        pass


def install(base: Any) -> None:
    def installed_find(page: Any) -> Any | None:
        return find_header_image_add_button(base, page)

    def installed_upload(page: Any, image_path: Path) -> None:
        upload_header_image(base, page, image_path)

    base._find_header_image_add_button = installed_find
    base._upload_header_image = installed_upload
