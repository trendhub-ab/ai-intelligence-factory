#!/usr/bin/env python3
"""Run317: save the exact member-onboarding rewrite to note's server and prove persistence.

Why this exists:
Run315/316 reused one persistent Chrome profile. A rewritten article could therefore remain
visible in that profile even when note's server still returned the legacy article to another
browser. Run317 treats same-profile visibility as insufficient evidence.

Safety contract:
- exact note ID n284e428c80f4 only;
- source must be the exact Run314 legacy state or the exact authorized Run315 rewrite;
- no publish-settings entry, no membership mutation, no public release;
- no Notion writes and zero Gemini/model calls;
- mutation occurs in a clean browser context that receives note.com cookies only;
- after clicking the exact visible `一時保存`, the browser is closed;
- persistence is proven in a second fresh browser/context with cookies only and no localStorage.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run315_member_onboarding_update as run315
import run315_member_onboarding_update_dom_range as range_adapter

CONFIRM_TOKEN = "SAVE_MEMBER_ONBOARDING_SERVER_N284E428C80F4_SHA4826AABC"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_SERVER_SAVE_RESULT_FILE"
NEW_BODY_SHA256 = "aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6"


def _headless() -> bool:
    return os.environ.get("NOTE_CHROME_HEADLESS", "false").strip().lower() in {"1", "true", "yes", "on"}


def _note_cookies(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        if not cloud._note_domain(str(item.get("domain") or "")):
            continue
        cookie = dict(item)
        same_site = cookie.get("sameSite")
        if same_site not in {None, "Strict", "Lax", "None"}:
            cookie.pop("sameSite", None)
        out.append(cookie)
    return out


def _launch_clean_browser(playwright: Any) -> Any:
    channel = os.environ.get("NOTE_CHROME_CHANNEL", "chrome").strip() or "chrome"
    return playwright.chromium.launch(
        channel=channel,
        headless=_headless(),
        args=["--lang=ja-JP", "--no-first-run", "--no-default-browser-check", "--disable-dev-shm-usage"],
    )


def _new_cookie_only_context(browser: Any, cookies: list[dict[str, Any]]) -> Any:
    context = browser.new_context(
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
        viewport={"width": 1440, "height": 1100},
    )
    if not cookies:
        raise base.NoteAuthenticationExpired("Run317 has no note.com authentication cookies")
    context.add_cookies(cookies)
    return context


def _open_exact_clean_editor(page: Any) -> tuple[Any, Any, str, str]:
    page.goto(run315.TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1400)
    if base._looks_logged_out(page):
        raise base.NoteAuthenticationExpired("Run317 clean browser is not authenticated to note")
    if not run315._is_exact_editor(str(page.url or "")):
        raise base.NoteDraftError("Run317 clean browser did not reach the exact onboarding editor")
    title_field = base._find_title(page)
    title = run315._field_text(title_field)
    body = base._find_body(page, title_field)
    body_text = run315._body_text(body)
    return title_field, body, title, body_text


def _source_state(title: str, body_text: str, body: Any) -> str:
    digest = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
    if title == run315.AUDITED_TITLE and digest == run315.AUDITED_BODY_SHA256:
        return "server_legacy_exact"
    if title == run315.NEW_TITLE and digest == NEW_BODY_SHA256:
        run315._verify_editor(body)
        return "server_new_exact"
    raise base.NoteDraftError(
        f"Run317 refuses unexpected clean-server source state: title={title!r} sha256={digest}"
    )


def _exact_temporary_save_button(page: Any) -> Any:
    buttons = page.locator("button:visible").filter(has_text="一時保存")
    matches: list[Any] = []
    for idx in range(buttons.count()):
        button = buttons.nth(idx)
        try:
            text = " ".join(str(button.inner_text() or "").split())
        except Exception:
            continue
        if text == "一時保存":
            matches.append(button)
    if len(matches) != 1:
        raise base.NoteDraftError(f"Run317 expected one exact visible 一時保存 button; got {len(matches)}")
    if not matches[0].is_enabled():
        raise base.NoteDraftError("Run317 exact 一時保存 button is disabled after authorized rewrite")
    return matches[0]


def _rewrite_and_save(page: Any, title_field: Any, body: Any) -> None:
    title_field = base._set_title(page, run315.NEW_TITLE)
    if run315._field_text(title_field) != run315.NEW_TITLE:
        raise base.NoteDraftError("Run317 new title did not appear in clean editor")
    body = base._find_body(page, title_field)
    range_adapter._paste_manuscript_dom_range(page, body, run315.MANUSCRIPT)
    body = base._find_body(page, title_field)
    base._verify_body_content(body, run315.MANUSCRIPT)
    run315._verify_editor(body)
    digest = hashlib.sha256(run315._body_text(body).encode("utf-8")).hexdigest()
    if digest != NEW_BODY_SHA256:
        raise base.NoteDraftError(f"Run317 rewritten body SHA mismatch before save: {digest}")
    _exact_temporary_save_button(page).click()
    page.wait_for_timeout(3000)


def _verify_fresh_server_state(playwright: Any, cookies: list[dict[str, Any]]) -> dict[str, Any]:
    # Deliberately launch a second browser/context. Do not pass storage_state, localStorage,
    # IndexedDB, or the persistent Chrome user-data directory into this proof browser.
    browser = _launch_clean_browser(playwright)
    try:
        context = _new_cookie_only_context(browser, cookies)
        try:
            page = context.new_page()
            page.set_default_timeout(30000)
            title_field, body, title, body_text = _open_exact_clean_editor(page)
            del title_field
            digest = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
            if title != run315.NEW_TITLE:
                raise base.NoteDraftError(f"Run317 fresh verification returned old/unexpected title: {title!r}")
            if digest != NEW_BODY_SHA256:
                raise base.NoteDraftError(f"Run317 fresh verification body SHA mismatch: {digest}")
            run315._verify_editor(body)
            return {
                "fresh_context_verified": True,
                "fresh_title": title,
                "fresh_body_sha256": digest,
                "fresh_context_local_storage_seeded": False,
            }
        finally:
            context.close()
    finally:
        browser.close()


def save_server_revision() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_SERVER_SAVE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run317 exact server-save confirmation token is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run317") from exc

    with sync_playwright() as playwright:
        # Persistent Chrome is used only as an authenticated cookie source. Article content is
        # never trusted from this profile because it may contain unsaved local editor state.
        persistent = cloud._launch_persistent_context(playwright)
        try:
            pages = list(persistent.pages)
            seed_page = pages[0] if pages else persistent.new_page()
            seed_page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
            seed_page.wait_for_timeout(700)
            cookies = _note_cookies(persistent.cookies())
            if not cookies:
                seeded = cloud._seed_note_state(persistent, seed_page)
                if seeded:
                    cookies = _note_cookies(persistent.cookies())
            if not cookies:
                raise base.NoteAuthenticationExpired("Run317 could not obtain note.com authentication cookies")
        finally:
            persistent.close()

        source_browser = _launch_clean_browser(playwright)
        try:
            source_context = _new_cookie_only_context(source_browser, cookies)
            try:
                page = source_context.new_page()
                page.set_default_timeout(30000)
                title_field, body, title, body_text = _open_exact_clean_editor(page)
                state = _source_state(title, body_text, body)
                rewritten = False
                temporary_save_clicked = False
                if state == "server_legacy_exact":
                    _rewrite_and_save(page, title_field, body)
                    rewritten = True
                    temporary_save_clicked = True
                # Capture refreshed authentication cookies only. No localStorage is exported.
                verification_cookies = _note_cookies(source_context.cookies())
                if not verification_cookies:
                    raise base.NoteAuthenticationExpired("Run317 source browser lost note.com cookies")
            finally:
                source_context.close()
        finally:
            source_browser.close()

        verified = _verify_fresh_server_state(playwright, verification_cookies)
        return {
            "status": "server_saved_and_verified",
            "target_note_id": run315.TARGET_NOTE_ID,
            "source_state": state,
            "rewritten": rewritten,
            "temporary_save_clicked": temporary_save_clicked,
            "server_mutation": rewritten,
            "public_release": False,
            "membership_mutation": False,
            "zero_gemini_calls": True,
            "notion_writes": 0,
            **verified,
        }


def main() -> None:
    result = save_server_revision()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN317_MEMBER_ONBOARDING_SERVER_SAVE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
