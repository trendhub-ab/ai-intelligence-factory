#!/usr/bin/env python3
"""Run330: update only the exact note profile biography through the Run329-proven route.

Safety contract:
- exact public account and exact legacy/current biography state only;
- verify the public `設定` href is exactly https://note.com/settings/profile, but never click it;
- mutate only textarea[name="editBiography"][aria-label="自己紹介"];
- preserve creator name and every other user-visible control in the biography's profile form;
- click exactly one visible enabled `保存` button exactly once when mutation is required;
- verify the public profile and a fresh settings read after save;
- idempotent no-op when the public/settings state is already current;
- zero Gemini/model calls and zero Notion writes.

Run331 hardening: the unrelated-setting invariant is scoped to the actual profile form and
semantic user-visible control state. Global header/search controls, hidden framework tokens,
DOM ordering, and transient disabled state are not customer settings and are excluded from the
post-save comparison. note renders real switch controls as transparent checkbox inputs, so
role="switch" controls remain explicitly included even when their input element is visually hidden.
This prevents a successful save from being reported as a false failure without dropping real
layout/menu settings from the invariant.
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
    """Snapshot semantic user settings in the form that owns the biography.

    Run330 originally compared every input on the whole page, including unrelated header
    controls and framework/transient state. note can legitimately re-render those after Save,
    which caused a false-positive failure even though the biography save succeeded. The current
    invariant follows the actual profile form, ignores the authorized biography itself, excludes
    non-visible implementation controls, but keeps role=switch inputs because note visually hides
    those checkbox elements while they still represent real customer settings. Stable semantic
    values are compared independent of DOM ordering.
    """
    raw = page.evaluate(
        r"""
        () => {
          const bio = document.querySelector('textarea[name="editBiography"][aria-label="自己紹介"]');
          if (!bio) return null;
          const root = bio.closest('form');
          if (!root) return null;
          const visible = (el) => {
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' &&
              style.visibility !== 'hidden' && style.opacity !== '0';
          };
          const rows = Array.from(root.querySelectorAll('input, textarea, select'))
            .filter(el => visible(el) || (el.getAttribute('role') || '') === 'switch')
            .filter(el => !(el.tagName.toLowerCase() === 'textarea' &&
              (el.getAttribute('name') || '') === 'editBiography' &&
              (el.getAttribute('aria-label') || '') === '自己紹介'))
            .map(el => ({
              tag: el.tagName.toLowerCase(),
              type: el.getAttribute('type') || '',
              role: el.getAttribute('role') || '',
              name: el.getAttribute('name') || '',
              ariaLabel: el.getAttribute('aria-label') || '',
              value: 'value' in el ? String(el.value || '') : '',
              checked: 'checked' in el ? Boolean(el.checked) : null,
            }));
          const counts = {};
          for (const row of rows) {
            const base = [row.tag, row.type, row.role, row.name, row.ariaLabel].join('|');
            const occurrence = counts[base] || 0;
            counts[base] = occurrence + 1;
            row.occurrence = occurrence;
          }
          rows.sort((a, b) => {
            const ka = [a.tag, a.type, a.role, a.name, a.ariaLabel, a.occurrence].join('|');
            const kb = [b.tag, b.type, b.role, b.name, b.ariaLabel, b.occurrence].join('|');
            return ka.localeCompare(kb);
          });
          return rows;
        }
        """
    )
    if not isinstance(raw, list):
        raise base.NoteDraftError("Run330 could not locate the profile form for settings snapshot")
    return raw


def _snapshot_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("tag"),
        row.get("type"),
        row.get("role"),
        row.get("name"),
        row.get("ariaLabel"),
        row.get("occurrence"),
    )


def _snapshot_diff(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> str:
    if before == after:
        return ""
    before_map = {_snapshot_key(row): row for row in before}
    after_map = {_snapshot_key(row): row for row in after}
    keys = sorted(set(before_map) | set(after_map), key=str)
    changed: list[str] = []
    for key in keys:
        left = before_map.get(key)
        right = after_map.get(key)
        if left != right:
            changed.append(f"{key!r}: {left!r} -> {right!r}")
        if len(changed) >= 6:
            break
    return " ; ".join(changed)[:1800]


def _require_snapshot_unchanged(before: list[dict[str, Any]], after: list[dict[str, Any]], stage: str) -> None:
    diff = _snapshot_diff(before, after)
    if diff:
        raise base.NoteDraftError(f"Run330 detected a non-biography profile-form change {stage}; diff: {diff}")


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
            _require_snapshot_unchanged(before_snapshot, _form_snapshot(page), "before save")

            save = _exact_save_control(page)
            save.click()
            save_clicks += 1
            page.wait_for_timeout(2200)
            if save_clicks != 1:
                raise base.NoteDraftError("Run330 exact-one-save contract failed")

            _require_snapshot_unchanged(before_snapshot, _form_snapshot(page), "after save")
            _verify_public_current(page)

            _, after_fresh_snapshot = _open_settings_and_assert_account(page, run311.CURRENT_PROFILE)
            _require_snapshot_unchanged(before_snapshot, after_fresh_snapshot, "on fresh settings verification")
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
