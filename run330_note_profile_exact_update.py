#!/usr/bin/env python3
"""Run330: update only the exact note profile biography through the Run329-proven route.

Safety contract:
- exact public account and exact legacy/current biography state only;
- verify the public `設定` href is exactly https://note.com/settings/profile, but never click it;
- mutate only textarea[name="editBiography"][aria-label="自己紹介"];
- preserve creator name and every other settings-form control value/state;
- click exactly one visible enabled `保存` button exactly once when mutation is required;
- verify the public profile and a fresh settings read after save;
- idempotent no-op when the public/settings state is already current;
- zero Gemini/model calls and zero Notion writes.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run311_note_profile_update as run311
import run329_note_profile_direct_route_probe as run329

CONFIRM_TOKEN = "UPDATE_NOTE_PROFILE_TRENDHUB_BIZ_RUN330_EXACT_BIOGRAPHY"
RESULT_ENV = "NOTE_PROFILE_RUN330_RESULT_FILE"
BIO_SELECTOR = 'textarea[name="editBiography"][aria-label="自己紹介"]:visible'
NICKNAME_SELECTOR = 'input[name="editNickname"][aria-label="クリエイター名"]:visible'
EXPECTED_NICKNAME = "AI Intelligence Factory"


def _canon(value: Any) -> str:
    return run311._canon(str(value or ""))


def _exact_single(page: Any, selector: str, label: str) -> Any:
    locator = page.locator(selector)
    count = locator.count()
    if count != 1:
        raise base.NoteDraftError(f"Run330 expected exactly one {label}; observed {count}")
    item = locator.first
    if not item.is_visible():
        raise base.NoteDraftError(f"Run330 {label} is not visible")
    return item


def _settings_href(page: Any) -> str:
    control = run311._settings_control(page)
    href = str(control.get_attribute("href") or "").strip()
    if href != run329.PROFILE_SETTINGS_URL:
        raise base.NoteDraftError(f"Run330 refuses unexpected profile settings href: {href!r}")
    return href


def _public_state(page: Any) -> str:
    page.goto(run311.PUBLIC_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1600)
    text = _canon(page.locator("body").inner_text(timeout=10000))
    legacy = _canon(run311.LEGACY_PROFILE)
    current = _canon(run311.CURRENT_PROFILE)
    has_legacy = legacy in text
    has_current = current in text
    if has_current and "Product Hunt" not in text:
        return "current"
    if has_legacy and "Product Hunt" in text and not has_current:
        return "legacy"
    raise base.NoteDraftError("Run330 refuses an unexpected public profile state")


def _form_snapshot(page: Any) -> list[dict[str, Any]]:
    """Snapshot settings controls excluding the authorized biography field.

    Dynamic React ids/classes are intentionally excluded. Ordering is retained so unnamed
    switches remain comparable. Search controls are included because they must also remain
    unchanged by this maintenance action.
    """
    raw = page.evaluate(
        r"""
        () => Array.from(document.querySelectorAll('input, textarea, select')).map((el, index) => ({
          index,
          tag: el.tagName.toLowerCase(),
          type: el.getAttribute('type') || '',
          name: el.getAttribute('name') || '',
          ariaLabel: el.getAttribute('aria-label') || '',
          value: 'value' in el ? String(el.value || '') : '',
          checked: 'checked' in el ? Boolean(el.checked) : null,
          disabled: Boolean(el.disabled),
        })).filter(row => !(row.tag === 'textarea' && row.name === 'editBiography' && row.ariaLabel === '自己紹介'))
        """
    )
    if not isinstance(raw, list):
        raise base.NoteDraftError("Run330 could not snapshot profile settings controls")
    return raw


def _open_settings_and_assert_account(page: Any, expected_bio: str) -> tuple[Any, list[dict[str, Any]]]:
    page.goto(run329.PROFILE_SETTINGS_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1600)
    if not str(page.url or "").startswith(run329.PROFILE_SETTINGS_URL):
        raise base.NoteDraftError(f"Run330 profile settings route redirected unexpectedly: {page.url!r}")

    bio = _exact_single(page, BIO_SELECTOR, "profile biography textarea")
    nickname = _exact_single(page, NICKNAME_SELECTOR, "creator-name input")
    if _canon(nickname.input_value()) != EXPECTED_NICKNAME:
        raise base.NoteDraftError("Run330 refuses an unexpected creator name")
    if _canon(bio.input_value()) != _canon(expected_bio):
        raise base.NoteDraftError("Run330 refuses biography text outside the exact expected state")
    return bio, _form_snapshot(page)


def _exact_save_control(page: Any) -> Any:
    pattern = re.compile(r"^\s*保存\s*$")
    candidates = page.locator("button:visible").filter(has_text=pattern)
    exact: list[Any] = []
    for idx in range(candidates.count()):
        item = candidates.nth(idx)
        if _canon(item.inner_text()) == "保存":
            exact.append(item)
    if len(exact) != 1:
        raise base.NoteDraftError(f"Run330 expected exactly one visible exact 保存 button; observed {len(exact)}")
    button = exact[0]
    if not button.is_enabled():
        raise base.NoteDraftError("Run330 exact 保存 button is disabled")
    return button


def _verify_public_current(page: Any) -> None:
    state = _public_state(page)
    if state != "current":
        raise base.NoteDraftError("Run330 public verification did not reach current profile state")


def update_profile() -> dict[str, Any]:
    if os.environ.get("NOTE_PROFILE_RUN330_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run330 exact profile-update confirmation token is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run330") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        save_clicks = 0
        try:
            public_state = _public_state(page)
            href = _settings_href(page)

            if public_state == "current":
                _, current_snapshot = _open_settings_and_assert_account(page, run311.CURRENT_PROFILE)
                _verify_public_current(page)
                return {
                    "status": "already_current_verified_no_mutation",
                    "public_profile_url": run311.PUBLIC_PROFILE_URL,
                    "settings_href_verified": href,
                    "biography_mutation": False,
                    "other_settings_unchanged": True,
                    "settings_snapshot_size": len(current_snapshot),
                    "save_clicks": 0,
                    "public_mutation": False,
                    "zero_gemini_calls": True,
                    "notion_writes": 0,
                }

            bio, before_snapshot = _open_settings_and_assert_account(page, run311.LEGACY_PROFILE)
            bio.fill(run311.CURRENT_PROFILE)
            page.wait_for_timeout(400)
            if _canon(bio.input_value()) != _canon(run311.CURRENT_PROFILE):
                raise base.NoteDraftError("Run330 biography field did not contain the exact authorized current copy")
            if _form_snapshot(page) != before_snapshot:
                raise base.NoteDraftError("Run330 detected a non-biography settings change before save")

            save = _exact_save_control(page)
            save.click()
            save_clicks += 1
            page.wait_for_timeout(2200)
            if save_clicks != 1:
                raise base.NoteDraftError("Run330 exact-one-save contract failed")

            if _form_snapshot(page) != before_snapshot:
                raise base.NoteDraftError("Run330 detected a non-biography settings change after save")

            _verify_public_current(page)

            _, after_fresh_snapshot = _open_settings_and_assert_account(page, run311.CURRENT_PROFILE)
            if after_fresh_snapshot != before_snapshot:
                raise base.NoteDraftError("Run330 fresh settings verification found an unrelated field change")
            _verify_public_current(page)

            return {
                "status": "updated_and_verified_exact_biography_only",
                "public_profile_url": run311.PUBLIC_PROFILE_URL,
                "settings_href_verified": href,
                "biography_mutation": True,
                "other_settings_unchanged": True,
                "settings_snapshot_size": len(before_snapshot),
                "save_clicks": save_clicks,
                "public_mutation": True,
                "product_hunt_removed": True,
                "zero_gemini_calls": True,
                "notion_writes": 0,
            }
        finally:
            context.close()


def main() -> None:
    result = update_profile()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN330_NOTE_PROFILE_EXACT_UPDATE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
