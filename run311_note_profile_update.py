#!/usr/bin/env python3
"""Run311: update only the AI Intelligence Factory note profile description.

This is a zero-model, exact-account maintenance action. It does not touch creator name,
images, SNS links, article publication, tags, membership settings, or any other note account.
The browser flow follows note's documented PC UI: creator page -> 設定 -> profile text -> 保存.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud

CONFIRM_TOKEN = "UPDATE_NOTE_PROFILE_TRENDHUB_BIZ"
PUBLIC_PROFILE_URL = "https://note.com/trendhub_biz"
RESULT_ENV = "NOTE_PROFILE_UPDATE_RESULT_FILE"
LEGACY_PROFILE = (
    "技術トレンド、多すぎませんか？ GitHub/HN/ArXiv/Product Huntから厳選し、"
    "「何が本当に大事か」を代替比較・乗り換えコストまで含めて分かりやすくお届けするnoteです。 "
    "※ AI×人の目で不定期更新中。"
)
CURRENT_PROFILE = (
    "AI・技術の「使える / まだ」を、一次情報とEvidenceから判断するAI Intelligence Factory。"
    "自分の開発、業務利用、必要に応じた提案に使えるDecision BriefとAI意思決定DBを運営しています。"
)


def _canon(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _visible_exact(page: Any, tag: str, text: str) -> Any:
    pattern = re.compile(rf"^\s*{re.escape(text)}\s*$")
    locator = page.locator(f"{tag}:visible").filter(has_text=pattern)
    try:
        locator.first.wait_for(state="visible", timeout=10000)
    except Exception as exc:
        raise base.NoteDraftError(f"Run311 could not observe visible {text} control") from exc
    visible = [_canon(v) for v in page.locator(f"{tag}:visible").all_text_contents()]
    if sum(value == text for value in visible) != 1:
        raise base.NoteDraftError(f"Run311 expected exactly one visible {text} control")
    return locator.first


def _settings_control(page: Any) -> Any:
    for tag in ("button", "a"):
        try:
            return _visible_exact(page, tag, "設定")
        except base.NoteDraftError:
            continue
    raise base.NoteDraftError("Run311 could not find the exact visible profile settings control")


def _field_value(locator: Any) -> str:
    try:
        tag = str(locator.evaluate("el => el.tagName.toLowerCase()"))
    except Exception:
        tag = ""
    if tag in {"textarea", "input"}:
        try:
            return str(locator.input_value() or "")
        except Exception:
            return ""
    try:
        return str(locator.inner_text() or "")
    except Exception:
        return ""


def _find_profile_field(page: Any) -> Any:
    legacy_marker = "Product Hunt"
    current_marker = "Decision Brief"
    for selector in ("textarea:visible", 'input:visible[type="text"]', '[contenteditable="true"]:visible'):
        locators = page.locator(selector)
        for idx in range(locators.count()):
            candidate = locators.nth(idx)
            value = _field_value(candidate)
            if legacy_marker in value or current_marker in value:
                return candidate
    raise base.NoteDraftError("Run311 could not identify the existing profile-description field")


def _set_profile_field(page: Any, field: Any, value: str) -> None:
    tag = str(field.evaluate("el => el.tagName.toLowerCase()"))
    if tag in {"textarea", "input"}:
        field.fill(value)
    else:
        field.click()
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(value)
    page.wait_for_timeout(500)
    if _canon(_field_value(field)) != _canon(value):
        raise base.NoteDraftError("Run311 profile field did not contain the authorized current copy")


def _save_control(page: Any) -> Any:
    for tag in ("button", "a"):
        try:
            return _visible_exact(page, tag, "保存")
        except base.NoteDraftError:
            continue
    raise base.NoteDraftError("Run311 could not find the exact visible profile save control")


def _verify_public(page: Any) -> None:
    page.goto(PUBLIC_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    text = _canon(str(page.locator("body").inner_text(timeout=10000) or ""))
    if _canon(CURRENT_PROFILE) not in text:
        raise base.NoteDraftError("Run311 public profile verification could not find current copy")
    if "Product Hunt" in text:
        raise base.NoteDraftError("Run311 public profile verification still contains Product Hunt")


def update_profile() -> dict[str, Any]:
    if os.environ.get("NOTE_PROFILE_UPDATE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run311 exact profile update confirmation token is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run311 note profile update") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(PUBLIC_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1300)
            public_text = _canon(str(page.locator("body").inner_text(timeout=10000) or ""))
            if _canon(CURRENT_PROFILE) in public_text and "Product Hunt" not in public_text:
                return {
                    "status": "already_current",
                    "public_mutation": False,
                    "zero_gemini_calls": True,
                    "public_profile_url": PUBLIC_PROFILE_URL,
                    "profile": CURRENT_PROFILE,
                }
            if "Product Hunt" not in public_text:
                raise base.NoteDraftError("Run311 refuses an unexpected public profile state")

            _settings_control(page).click()
            page.wait_for_timeout(1000)
            field = _find_profile_field(page)
            current_value = _canon(_field_value(field))
            if current_value == _canon(CURRENT_PROFILE):
                _verify_public(page)
                return {
                    "status": "already_current",
                    "public_mutation": False,
                    "zero_gemini_calls": True,
                    "public_profile_url": PUBLIC_PROFILE_URL,
                    "profile": CURRENT_PROFILE,
                }
            if current_value != _canon(LEGACY_PROFILE):
                raise base.NoteDraftError("Run311 refuses profile text that does not match the audited legacy copy")

            _set_profile_field(page, field, CURRENT_PROFILE)
            _save_control(page).click()
            page.wait_for_timeout(1800)
            _verify_public(page)
            return {
                "status": "updated_and_verified",
                "public_mutation": True,
                "zero_gemini_calls": True,
                "public_profile_url": PUBLIC_PROFILE_URL,
                "profile": CURRENT_PROFILE,
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
    print("RUN311_NOTE_PROFILE_UPDATE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
