#!/usr/bin/env python3
"""Run337: logged-out, zero-click audit of the public membership purchase surface.

Run335 proved the saved membership description and the public creator-card state are current.
Run337 closes the next customer-facing gap by checking the actual membership landing/purchase page
from a fresh browser with no seeded cookies or storage.

Safety contract:
- exact public membership URL only;
- fresh no-cookie/no-storage browser context;
- navigation + DOM reads + screenshot only;
- no clicks, fills, submissions, editor/settings routes, or note mutation;
- zero Gemini/model calls and zero Notion writes.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run311_note_profile_update as run311
import run317_member_onboarding_server_save as run317
import run326_member_onboarding_public_audit as run326
import run333_membership_description_exact_update as run333

CONFIRM_TOKEN = "AUDIT_PUBLIC_MEMBERSHIP_FUNNEL_TRENDHUB_BIZ_RUN337_LOGGED_OUT"
RESULT_ENV = "NOTE_MEMBERSHIP_PUBLIC_RUN337_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_MEMBERSHIP_PUBLIC_RUN337_SCREENSHOT_FILE"
PUBLIC_MEMBERSHIP_URL = "https://note.com/trendhub_biz/membership"

JOIN_TOKENS = ("参加", "加入", "入会", "申し込", "はじめる", "始める")
JOIN_HREF_TOKENS = ("/join", "join?", "membership/join", "membership/subscribe", "membership/register")
NOT_AVAILABLE_MARKERS = (
    "現在販売されていません",
    "現在募集していません",
    "このメンバーシップは終了しました",
    "このプランは終了しました",
)


def _canon(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _price_verified(text: str) -> bool:
    compact = re.sub(r"\s+", "", str(text or ""))
    return bool(re.search(r"(?:¥|￥)?1,980(?:円)?(?:/月|円/月|月額)", compact))


def _visible_actions(page: Any) -> list[dict[str, str]]:
    rows = page.locator("button:visible, a:visible")
    out: list[dict[str, str]] = []
    for idx in range(rows.count()):
        item = rows.nth(idx)
        try:
            out.append(
                {
                    "text": _canon(item.inner_text(timeout=3000)),
                    "ariaLabel": _canon(item.get_attribute("aria-label")),
                    "href": str(item.get_attribute("href") or "").strip(),
                }
            )
        except Exception:
            continue
    return out


def _join_candidates(actions: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for row in actions:
        label = _canon(f"{row.get('text', '')} {row.get('ariaLabel', '')}")
        href = str(row.get("href") or "").lower()
        if any(token in label for token in JOIN_TOKENS) or any(token in href for token in JOIN_HREF_TOKENS):
            result.append(row)
    return result


def audit() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBERSHIP_PUBLIC_RUN337_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run337 exact logged-out membership-audit confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run337") from exc

    with sync_playwright() as playwright:
        browser = run317._launch_clean_browser(playwright)
        try:
            context = browser.new_context(
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                viewport={"width": 1440, "height": 1200},
            )
            try:
                cookies_before = context.cookies()
                if cookies_before:
                    raise base.NoteDraftError("Run337 fresh context unexpectedly contains cookies before navigation")

                page = context.new_page()
                page.set_default_timeout(30000)
                response = page.goto(PUBLIC_MEMBERSHIP_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2600)

                final_url = str(page.url or "")
                if not final_url.startswith(PUBLIC_MEMBERSHIP_URL):
                    raise base.NoteDraftError(f"Run337 public membership URL drifted: {final_url!r}")

                body_text = _canon(page.locator("body").inner_text(timeout=10000))
                page_title = _canon(page.title())
                http_status = response.status if response is not None else None

                challenge_hits = [m for m in run326.BOT_OR_CHALLENGE_MARKERS if m.lower() in body_text.lower()]
                if challenge_hits:
                    raise base.NoteDraftError(f"Run337 membership page is blocked by challenge: {challenge_hits}")

                not_available_hits = [m for m in NOT_AVAILABLE_MARKERS if m in body_text]
                if not_available_hits:
                    raise base.NoteDraftError(f"Run337 membership page reports unavailable state: {not_available_hits}")

                membership_verified = run333.MEMBERSHIP_NAME in body_text
                if not membership_verified:
                    raise base.NoteDraftError("Run337 public membership page does not expose AI Decision Intelligence")

                current_description = _canon(run333.NEW_DESCRIPTION)
                legacy_description = _canon(run333.OLD_DESCRIPTION)
                description_verified = current_description in body_text
                legacy_description_absent = legacy_description not in body_text and run326._canon(run333.run332.LEGACY_REFERENCE) not in body_text
                if not description_verified:
                    raise base.NoteDraftError("Run337 public purchase surface does not expose the current 114-character plan description")
                if not legacy_description_absent:
                    raise base.NoteDraftError("Run337 public purchase surface still exposes the legacy onboarding article reference")

                price_verified = _price_verified(body_text)
                if not price_verified:
                    raise base.NoteDraftError("Run337 could not verify the ¥1,980/month public plan price")

                stale_profile_absent = _canon(run311.LEGACY_PROFILE) not in body_text
                if not stale_profile_absent:
                    raise base.NoteDraftError("Run337 public membership surface still exposes the retired Product Hunt profile copy")
                current_profile_visible = _canon(run311.CURRENT_PROFILE) in body_text

                actions = _visible_actions(page)
                joins = _join_candidates(actions)
                if not joins:
                    raise base.NoteDraftError("Run337 could not identify any visible join/signup action on the public membership surface")

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
                        if name != run326.ANONYMOUS_NOTE_SESSION_COOKIE
                        and any(token in name.lower() for token in ("auth", "token", "login", "user_id"))
                    }
                )
                if explicit_auth_cookie_names:
                    raise base.NoteDraftError(
                        f"Run337 fresh public context unexpectedly acquired explicit auth cookies: {explicit_auth_cookie_names}"
                    )

                screenshot_file = os.environ.get(SCREENSHOT_ENV, "").strip()
                if screenshot_file:
                    path = Path(screenshot_file)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(path), full_page=True)

                return {
                    "status": "logged_out_membership_purchase_surface_verified",
                    "public_url": PUBLIC_MEMBERSHIP_URL,
                    "final_url": final_url,
                    "http_status": http_status,
                    "page_title": page_title,
                    "membership_name_verified": membership_verified,
                    "price_1980_month_verified": price_verified,
                    "current_description_verified": description_verified,
                    "legacy_description_absent": legacy_description_absent,
                    "stale_profile_absent": stale_profile_absent,
                    "current_profile_visible": current_profile_visible,
                    "join_action_verified": True,
                    "join_candidates": joins[:12],
                    "not_available_hits": not_available_hits,
                    "cookies_before_navigation": [],
                    "note_cookie_names_after": note_cookie_names_after,
                    "anonymous_note_session_seen": run326.ANONYMOUS_NOTE_SESSION_COOKIE in note_cookie_names_after,
                    "explicit_auth_cookie_names_after": explicit_auth_cookie_names,
                    "fresh_no_cookie_context": True,
                    "body_visible_chars": len(body_text),
                    "body_excerpt": body_text[:8000],
                    "screenshot_written": bool(screenshot_file),
                    "clicks_performed": 0,
                    "field_filled": False,
                    "save_clicked": False,
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
    print("RUN337_MEMBERSHIP_PUBLIC_FUNNEL_AUDIT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
