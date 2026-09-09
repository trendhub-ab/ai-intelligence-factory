#!/usr/bin/env python3
"""Run328: inspect current note profile-settings UI without saving anything.

The exact Run311 updater failed closed after clicking the public creator-page `設定` control
because note's current UI no longer exposed the profile description as a visible textarea/input/
contenteditable/textbox. Run328 reproduces only that navigation, then inventories the resulting
surface. It never fills text, never clicks Save, and never changes note/account state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run311_note_profile_update as run311

CONFIRM_TOKEN = "PROBE_NOTE_PROFILE_SETTINGS_TRENDHUB_BIZ_READONLY"
RESULT_ENV = "NOTE_PROFILE_SETTINGS_PROBE_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_PROFILE_SETTINGS_PROBE_SCREENSHOT_FILE"


def _canon(value: Any) -> str:
    return run311._canon(str(value or ""))


def _surface(page: Any) -> dict[str, Any]:
    script = r"""
    () => {
      const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
      };
      const row = (el, index) => ({
        index,
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') || '',
        type: el.getAttribute('type') || '',
        name: el.getAttribute('name') || '',
        id: el.id || '',
        placeholder: el.getAttribute('placeholder') || '',
        ariaLabel: el.getAttribute('aria-label') || '',
        ariaDescribedby: el.getAttribute('aria-describedby') || '',
        contenteditable: el.getAttribute('contenteditable') || '',
        value: 'value' in el ? String(el.value || '').slice(0,1200) : '',
        text: norm(el.innerText || el.textContent || '').slice(0,1600),
        visible: visible(el),
        disabled: !!el.disabled,
        className: String(el.className || '').slice(0,1000),
      });
      const selector = [
        'textarea','input','button','a[href]','select','[contenteditable]','[role]',
        '[data-testid]','[data-test-id]','form','label'
      ].join(',');
      const nodes = Array.from(document.querySelectorAll(selector)).slice(0,1400).map(row);
      const entryCandidates = nodes.filter(r =>
        ['textarea','input'].includes(r.tag) || r.contenteditable || r.role === 'textbox'
      ).slice(0,300);
      const actionCandidates = nodes.filter(r => {
        const blob = `${r.text} ${r.ariaLabel} ${r.name} ${r.id}`;
        return /(保存|変更|プロフィール|自己紹介|説明|紹介文|編集|save|profile|description|bio)/i.test(blob);
      }).slice(0,300);
      const dialogs = Array.from(document.querySelectorAll('[role="dialog"]')).map(row).slice(0,50);
      const forms = Array.from(document.forms).map(row).slice(0,50);
      const body = norm(document.body ? document.body.innerText : '');
      const html = document.documentElement ? document.documentElement.outerHTML : '';
      const needles = ['Product Hunt','Decision Brief','プロフィール','自己紹介','説明','紹介文','保存'];
      const matches = {};
      for (const needle of needles) {
        matches[needle] = {
          body: body.includes(needle),
          html: html.includes(needle),
        };
      }
      return {
        url: location.href,
        title: document.title,
        readyState: document.readyState,
        bodyText: body.slice(0,30000),
        entryCandidates,
        actionCandidates,
        dialogs,
        forms,
        keywordMatches: matches,
      };
    }
    """
    result = page.evaluate(script)
    return result if isinstance(result, dict) else {"error": "non-dict surface"}


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_PROFILE_SETTINGS_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run328 exact read-only profile probe confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run328") from exc

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
                    "public_profile_url": run311.PUBLIC_PROFILE_URL,
                    "public_mutation": False,
                    "settings_mutation": False,
                    "clicks_performed": 0,
                    "zero_gemini_calls": True,
                    "notion_writes": 0,
                }
            if "Product Hunt" not in public_text or _canon(run311.LEGACY_PROFILE) not in public_text:
                raise base.NoteDraftError("Run328 refuses a public profile state outside the exact legacy/current contract")

            pre_url = str(page.url or "")
            run311._settings_control(page).click()
            page.wait_for_timeout(1100)
            surface_t1 = _surface(page)
            page.wait_for_timeout(1800)
            surface_t3 = _surface(page)

            screenshot_file = os.environ.get(SCREENSHOT_ENV, "").strip()
            if screenshot_file:
                path = Path(screenshot_file)
                path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(path), full_page=True)

            return {
                "status": "profile_settings_surface_probed_no_mutation",
                "public_profile_url": run311.PUBLIC_PROFILE_URL,
                "legacy_profile_verified_before_probe": True,
                "url_before_settings": pre_url,
                "url_after_settings": str(page.url or ""),
                "surface_t1": surface_t1,
                "surface_t3": surface_t3,
                "settings_control_clicked": True,
                "save_control_clicked": False,
                "field_filled": False,
                "public_mutation": False,
                "settings_mutation": False,
                "clicks_performed": 1,
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
    print("RUN328_NOTE_PROFILE_SETTINGS_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
