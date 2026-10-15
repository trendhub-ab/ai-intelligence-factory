#!/usr/bin/env python3
"""Run329: inspect note's exact profile-settings route without clicking or saving.

Run328 proved the visible creator-page `設定` control resolves to
https://note.com/settings/profile but a foreground note modal can intercept pointer events.
Run329 therefore treats the audited href as the authority, verifies it exactly, then navigates
directly to that route even when the public biography is already current. It records only
sanitized input structure needed to diagnose the production creator selector: no input values,
body text, HTML dump, UI click, input, save action, or profile/settings/public mutation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run311_note_profile_update as run311

CONFIRM_TOKEN = "PROBE_NOTE_PROFILE_DIRECT_ROUTE_TRENDHUB_BIZ_READONLY"
PROFILE_SETTINGS_URL = "https://note.com/settings/profile"
RESULT_ENV = "NOTE_PROFILE_DIRECT_PROBE_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_PROFILE_DIRECT_PROBE_SCREENSHOT_FILE"


def _canon(value: Any) -> str:
    return run311._canon(str(value or ""))


def _creator_selector_surface(page: Any) -> dict[str, Any]:
    selector = cloud.CREATOR_NAME_SELECTOR
    exact = page.locator(selector)
    try:
        creator_selector_count = exact.count()
    except Exception:
        creator_selector_count = -1

    creator_visible_count = 0
    if creator_selector_count > 0:
        for index in range(min(creator_selector_count, 20)):
            try:
                if exact.nth(index).is_visible(timeout=500):
                    creator_visible_count += 1
            except Exception:
                continue

    try:
        candidate_inputs = page.locator("input").evaluate_all(
            """
            els => els.slice(0, 100).map(el => {
              const r = el.getBoundingClientRect();
              const s = getComputedStyle(el);
              const visible = r.width > 0 && r.height > 0 && s.display !== 'none' &&
                              s.visibility !== 'hidden' && s.opacity !== '0';
              return {
                "tag": el.tagName.toLowerCase(),
                "name": el.getAttribute('name') || '',
                "ariaLabel": el.getAttribute('aria-label') || '',
                "type": el.getAttribute('type') || '',
                "visible": visible,
              };
            })
            """
        )
    except Exception:
        candidate_inputs = []

    return {
        "creator_selector": selector,
        "creator_selector_count": creator_selector_count,
        "creator_visible_count": creator_visible_count,
        "candidate_inputs": candidate_inputs if isinstance(candidate_inputs, list) else [],
    }


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_PROFILE_DIRECT_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run329 exact read-only direct-route confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run329") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(run311.PUBLIC_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1400)
            public_text = _canon(page.locator("body").inner_text(timeout=10000))
            current_profile_detected = (
                _canon(run311.CURRENT_PROFILE) in public_text and "Product Hunt" not in public_text
            )
            legacy_profile_detected = (
                "Product Hunt" in public_text and _canon(run311.LEGACY_PROFILE) in public_text
            )
            if not current_profile_detected and not legacy_profile_detected:
                raise base.NoteDraftError("Run329 refuses a public profile state outside the exact legacy/current contract")

            control = run311._settings_control(page)
            href = str(control.get_attribute("href") or "").strip()
            if href != PROFILE_SETTINGS_URL:
                raise base.NoteDraftError(f"Run329 refuses unexpected profile settings href: {href!r}")

            page.goto(PROFILE_SETTINGS_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            selector_surface_t1 = _creator_selector_surface(page)
            page.wait_for_timeout(1800)
            selector_surface_t3 = _creator_selector_surface(page)

            final_url = str(page.url or "")
            if not final_url.startswith(PROFILE_SETTINGS_URL):
                raise base.NoteDraftError(f"Run329 direct route did not remain on profile settings: {final_url!r}")

            screenshot_file = os.environ.get(SCREENSHOT_ENV, "").strip()
            if screenshot_file:
                path = Path(screenshot_file)
                path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(path), full_page=True)

            return {
                "status": "profile_settings_direct_route_probed_no_mutation",
                "public_profile_url": run311.PUBLIC_PROFILE_URL,
                "current_profile_detected": current_profile_detected,
                "legacy_profile_detected": legacy_profile_detected,
                "legacy_profile_verified_before_probe": legacy_profile_detected,
                "settings_href_verified": href,
                "url_after_direct_navigation": final_url,
                "selector_surface_t1": selector_surface_t1,
                "selector_surface_t3": selector_surface_t3,
                "settings_control_clicked": False,
                "save_control_clicked": False,
                "field_filled": False,
                "public_mutation": False,
                "settings_mutation": False,
                "clicks_performed": 0,
                "zero_gemini_calls": True,
                "notion_writes": 0,
                "screenshot_written": bool(screenshot_file),
            }
        finally:
            context.close()


def main() -> None:
    result = probe()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN329_NOTE_PROFILE_DIRECT_ROUTE_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
