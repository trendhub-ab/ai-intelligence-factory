#!/usr/bin/env python3
"""Run326: read-only, logged-out audit of the published member-onboarding note.

Run325 successfully finalized the exact latest draft for n284e428c80f4 while preserving
AI Decision Intelligence membership access and leaving the trial-read line unset. Run326
verifies the customer-facing surface from a fresh browser with NO cookies/storage state.

Run326b correction: note.com issues `_note_session_v5` even to a fresh logged-out visitor.
That server-created anonymous session cookie is not evidence that authentication was seeded.
The authentication invariant is therefore: the browser starts with zero cookies/storage,
no state is ever injected, and no explicit auth/token cookie is acquired.

Safety contract:
- exact public URL only;
- fresh no-cookie/no-storage browser context;
- navigation + DOM reads + screenshot only;
- no editor URL, no clicks, no form submission, no note/account mutation;
- zero Gemini/model calls and zero Notion writes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run315_member_onboarding_update as run315
import run317_member_onboarding_server_save as run317

CONFIRM_TOKEN = "AUDIT_PUBLIC_MEMBER_ONBOARDING_N284E428C80F4_SHAAAB9E57B_LOGGED_OUT"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_PUBLIC_AUDIT_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_MEMBER_ONBOARDING_PUBLIC_AUDIT_SCREENSHOT_FILE"
ANONYMOUS_NOTE_SESSION_COOKIE = "_note_session_v5"

# Markers from well below the public introduction. With no trial-read line configured,
# these must not be exposed to a logged-out visitor.
PROTECTED_BODY_MARKERS = (
    "AI意思決定DBを開く",
    "判断メモを開く",
    "4つの判断だけ覚えてください",
    "会員資格が終了した場合",
)
GATE_MARKERS = (
    "メンバーシップ",
    "メンバー限定",
    "メンバー",
    "加入",
    "購読者",
)
BOT_OR_CHALLENGE_MARKERS = (
    "Access Denied",
    "Cloudflare",
    "captcha",
    "CAPTCHA",
    "ロボットではない",
    "セキュリティチェック",
)
NOT_FOR_SALE_MARKERS = (
    "この記事は現在販売されていません",
    "この記事は現在販売していません",
)


def _canon(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _meta_content(page: Any, selector: str) -> str:
    try:
        item = page.locator(selector).first
        if item.count() < 1:
            return ""
        return _canon(item.get_attribute("content"))
    except Exception:
        return ""


def audit() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_PUBLIC_AUDIT_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run326 exact logged-out public-audit confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run326") from exc

    with sync_playwright() as playwright:
        browser = run317._launch_clean_browser(playwright)
        try:
            context = browser.new_context(
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                viewport={"width": 1440, "height": 1200},
            )
            try:
                # Critical external-view invariant: no authentication/browser state is seeded.
                cookies_before = context.cookies()
                if cookies_before:
                    raise base.NoteDraftError("Run326 fresh context unexpectedly contains cookies before navigation")

                page = context.new_page()
                page.set_default_timeout(30000)
                response = page.goto(run315.TARGET_PUBLIC_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2200)

                final_url = str(page.url or "")
                if not final_url.startswith(run315.TARGET_PUBLIC_URL):
                    raise base.NoteDraftError(f"Run326 public URL drifted: {final_url}")

                body_text = _canon(page.locator("body").inner_text(timeout=10000))
                page_title = _canon(page.title())
                og_title = _meta_content(page, 'meta[property="og:title"]')
                description = _meta_content(page, 'meta[name="description"]')
                http_status = response.status if response is not None else None

                challenge_hits = [m for m in BOT_OR_CHALLENGE_MARKERS if m.lower() in body_text.lower()]
                if challenge_hits:
                    raise base.NoteDraftError(f"Run326 public page is blocked by challenge: {challenge_hits}")

                not_for_sale_hits = [m for m in NOT_FOR_SALE_MARKERS if m in body_text]
                if not_for_sale_hits:
                    raise base.NoteDraftError(f"Run326 public page still reports not-for-sale: {not_for_sale_hits}")

                title_sources = [body_text, page_title, og_title]
                new_title_visible = any(run315.NEW_TITLE in source for source in title_sources)
                old_title_visible = any(run315.AUDITED_TITLE in source for source in title_sources)
                if not new_title_visible:
                    raise base.NoteDraftError(
                        f"Run326 public page does not expose the new title: page_title={page_title!r} og_title={og_title!r}"
                    )
                if old_title_visible:
                    raise base.NoteDraftError("Run326 logged-out public surface still exposes the legacy title")

                protected_hits = [m for m in PROTECTED_BODY_MARKERS if m in body_text]
                if protected_hits:
                    raise base.NoteDraftError(
                        f"Run326 logged-out visitor can see protected full-body markers: {protected_hits}"
                    )

                gate_hits = [m for m in GATE_MARKERS if m in body_text]
                if not gate_hits:
                    raise base.NoteDraftError(
                        "Run326 could not prove a member/subscriber gate on the logged-out public surface"
                    )

                # note.com is allowed to create an anonymous server session after first navigation.
                # Because this context started with zero cookies and no storage was injected, that
                # cookie cannot represent pre-existing user authentication. Fail only on explicit
                # auth/token-like cookies; record the anonymous session separately for auditability.
                cookies_after = context.cookies()
                note_cookie_names_after = sorted(
                    {
                        str(item.get("name") or "")
                        for item in cookies_after
                        if str(item.get("domain") or "").endswith("note.com")
                    }
                )
                explicit_auth_cookie_names = sorted(
                    {
                        name
                        for name in note_cookie_names_after
                        if name != ANONYMOUS_NOTE_SESSION_COOKIE
                        and any(token in name.lower() for token in ("auth", "token", "login", "user_id"))
                    }
                )
                if explicit_auth_cookie_names:
                    raise base.NoteDraftError(
                        f"Run326 fresh public context unexpectedly acquired explicit auth cookies: {explicit_auth_cookie_names}"
                    )

                screenshot_file = os.environ.get(SCREENSHOT_ENV, "").strip()
                if screenshot_file:
                    path = Path(screenshot_file)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(path), full_page=True)

                return {
                    "status": "logged_out_public_surface_verified",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "public_url": run315.TARGET_PUBLIC_URL,
                    "final_url": final_url,
                    "http_status": http_status,
                    "page_title": page_title,
                    "og_title": og_title,
                    "description": description,
                    "new_title_verified": True,
                    "legacy_title_absent": True,
                    "not_for_sale_absent": True,
                    "protected_body_markers_exposed": protected_hits,
                    "gate_markers_seen": gate_hits,
                    "members_only_gate_verified": True,
                    "cookies_before_navigation": [],
                    "note_cookie_names_after": note_cookie_names_after,
                    "anonymous_note_session_seen": ANONYMOUS_NOTE_SESSION_COOKIE in note_cookie_names_after,
                    "explicit_auth_cookie_names_after": explicit_auth_cookie_names,
                    "fresh_no_cookie_context": True,
                    "body_visible_chars": len(body_text),
                    "body_excerpt": body_text[:8000],
                    "screenshot_written": bool(screenshot_file),
                    "clicks_performed": 0,
                    "content_mutation": False,
                    "settings_mutation": False,
                    "membership_mutation": False,
                    "public_mutation": False,
                    "zero_gemini_calls": True,
                    "notion_writes": 0,
                }
            finally:
                context.close()
        finally:
            browser.close()


def main() -> None:
    result = audit()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN326_MEMBER_ONBOARDING_PUBLIC_AUDIT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
