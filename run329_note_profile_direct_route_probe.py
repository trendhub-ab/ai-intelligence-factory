#!/usr/bin/env python3
"""Run329: inspect note's exact profile-settings route without clicking or saving.

Run328 proved the visible creator-page `設定` control resolves to
https://note.com/settings/profile but a foreground note modal can intercept pointer events.
Run329 therefore treats the audited href as the authority, verifies it exactly, then navigates
directly to that route and inventories the settings surface. It performs zero UI clicks,
zero input, zero save actions, zero profile/settings/public mutations.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run311_note_profile_update as run311
import run328_note_profile_settings_probe as run328

CONFIRM_TOKEN = "PROBE_NOTE_PROFILE_DIRECT_ROUTE_TRENDHUB_BIZ_READONLY"
PROFILE_SETTINGS_URL = "https://note.com/settings/profile"
RESULT_ENV = "NOTE_PROFILE_DIRECT_PROBE_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_PROFILE_DIRECT_PROBE_SCREENSHOT_FILE"


def _canon(value: Any) -> str:
    return run311._canon(str(value or ""))


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
            if _canon(run311.CURRENT_PROFILE) in public_text and "Product Hunt" not in public_text:
                return {
                    "status": "already_current_no_probe_needed",
                    "public_mutation": False,
                    "settings_mutation": False,
                    "clicks_performed": 0,
                    "zero_gemini_calls": True,
                    "notion_writes": 0,
                }
            if "Product Hunt" not in public_text or _canon(run311.LEGACY_PROFILE) not in public_text:
                raise base.NoteDraftError("Run329 refuses a public profile state outside the exact legacy/current contract")

            control = run311._settings_control(page)
            href = str(control.get_attribute("href") or "").strip()
            if href != PROFILE_SETTINGS_URL:
                raise base.NoteDraftError(f"Run329 refuses unexpected profile settings href: {href!r}")

            pre_surface = run328._surface(page)
            page.goto(PROFILE_SETTINGS_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            surface_t1 = run328._surface(page)
            page.wait_for_timeout(1800)
            surface_t3 = run328._surface(page)

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
                "legacy_profile_verified_before_probe": True,
                "settings_href_verified": href,
                "url_after_direct_navigation": final_url,
                "pre_surface": pre_surface,
                "surface_t1": surface_t1,
                "surface_t3": surface_t3,
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
