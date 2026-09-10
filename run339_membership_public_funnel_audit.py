#!/usr/bin/env python3
"""Run339b: hydration-aware, logged-out audit of the public membership purchase surface.

Run337 failed at the first DOM read. Run338 proved note initially serves /membership as a
client-rendering shell, then hydrates the complete customer surface and transitions to
/membership/join. The first Run339 correction still checked the final URL too early, immediately
after DOMContentLoaded. Run339b fixes only that ordering bug: hydrate first, then verify the exact
client-side final route.

Run338 also proved `note_gql_auth_token` is issued to a fresh logged-out visitor while the page
still visibly exposes `ログイン` and `会員登録`. That token is therefore anonymous only under that
positive logged-out UI proof; unknown auth-like cookies remain fail-closed.

Safety contract:
- fresh browser with zero seeded cookies/storage;
- exact /membership start URL and exact /membership/join post-hydration final URL only;
- bounded wait for proven customer markers before client-route verification;
- `note_gql_auth_token` is anonymous only when logged-out UI is positively verified;
- every other auth/token/login/user_id-like cookie remains fail-closed;
- navigation + DOM reads + screenshot only; zero clicks/fills/saves/mutations;
- zero Gemini/model calls and zero Notion writes.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run311_note_profile_update as run311
import run315_member_onboarding_update as run315
import run317_member_onboarding_server_save as run317
import run326_member_onboarding_public_audit as run326
import run332_membership_description_edit_route_probe as run332
import run333_membership_description_exact_update as run333
import run337_membership_public_funnel_audit as run337

CONFIRM_TOKEN = "AUDIT_PUBLIC_MEMBERSHIP_FUNNEL_TRENDHUB_BIZ_RUN339B_POST_HYDRATION_LOGGED_OUT"
RESULT_ENV = "NOTE_MEMBERSHIP_PUBLIC_RUN339_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_MEMBERSHIP_PUBLIC_RUN339_SCREENSHOT_FILE"
PUBLIC_MEMBERSHIP_URL = run337.PUBLIC_MEMBERSHIP_URL
PUBLIC_MEMBERSHIP_JOIN_URL = PUBLIC_MEMBERSHIP_URL + "/join"
ANONYMOUS_LOGGED_OUT_AUTHLIKE_COOKIE = "note_gql_auth_token"
HYDRATION_TIMEOUT_MS = 12000
HYDRATION_POLL_MS = 250
REDIRECT_TIMEOUT_MS = 3000
EXPECTED_BENEFITS = (
    "AI Decision Intelligence｜会員向け意思決定DB",
    "AI Decision Intelligence｜会員向けDigest",
)


def _canon(value: Any) -> str:
    return run337._canon(value)


def _logged_out_ui_verified(actions: list[dict[str, str]]) -> bool:
    texts = {_canon(row.get("text")) for row in actions}
    return "ログイン" in texts and "会員登録" in texts


def _explicit_auth_cookie_names(cookie_names: list[str], logged_out_ui_verified: bool) -> list[str]:
    allowed = {run326.ANONYMOUS_NOTE_SESSION_COOKIE}
    if logged_out_ui_verified:
        allowed.add(ANONYMOUS_LOGGED_OUT_AUTHLIKE_COOKIE)
    return sorted(
        name
        for name in cookie_names
        if name not in allowed
        and any(token in name.lower() for token in ("auth", "token", "login", "user_id"))
    )


def _hydrated_customer_state(body_text: str, actions: list[dict[str, str]]) -> bool:
    body = _canon(body_text)
    return bool(
        run333.MEMBERSHIP_NAME in body
        and _canon(run333.NEW_DESCRIPTION) in body
        and run337._price_verified(body)
        and run337._join_candidates(actions)
        and _logged_out_ui_verified(actions)
    )


def _wait_for_hydrated_purchase_surface(page: Any, timeout_ms: int = HYDRATION_TIMEOUT_MS) -> tuple[str, list[dict[str, str]], int]:
    start = time.monotonic()
    deadline = start + max(1, timeout_ms) / 1000.0
    last_body = ""
    last_actions: list[dict[str, str]] = []
    while True:
        last_body = _canon(page.locator("body").inner_text(timeout=10000))
        last_actions = run337._visible_actions(page)
        if _hydrated_customer_state(last_body, last_actions):
            return last_body, last_actions, int((time.monotonic() - start) * 1000)
        if time.monotonic() >= deadline:
            raise base.NoteDraftError(
                "Run339b timed out waiting for hydrated logged-out purchase surface: "
                f"url={page.url!r} body_excerpt={last_body[:1200]!r}"
            )
        page.wait_for_timeout(HYDRATION_POLL_MS)


def _exact_onboarding_link_verified(page: Any, body_text: str) -> bool:
    if run315.NEW_TITLE not in body_text:
        return False
    links = page.locator(f'a[href="{run315.TARGET_PUBLIC_URL}"]:visible')
    return links.count() >= 1


def audit() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBERSHIP_PUBLIC_RUN339_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run339b exact logged-out membership-audit confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run339b") from exc

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
                    raise base.NoteDraftError("Run339b fresh context unexpectedly contains cookies before navigation")

                page = context.new_page()
                page.set_default_timeout(30000)
                response = page.goto(PUBLIC_MEMBERSHIP_URL, wait_until="domcontentloaded", timeout=60000)
                initial_url = str(page.url or "")

                http_status = response.status if response is not None else None
                if http_status != 200:
                    raise base.NoteDraftError(f"Run339b public membership HTTP status is not 200: {http_status!r}")

                # Run338 proved the client route can still be /membership at DOMContentLoaded.
                # First wait for the real customer surface; only then enforce the final /join route.
                body_text, actions, hydration_wait_ms = _wait_for_hydrated_purchase_surface(page)
                try:
                    page.wait_for_url(PUBLIC_MEMBERSHIP_JOIN_URL, timeout=REDIRECT_TIMEOUT_MS)
                except Exception as exc:
                    raise base.NoteDraftError(
                        f"Run339b hydrated surface did not converge to exact join route: {page.url!r}"
                    ) from exc
                final_url = str(page.url or "")
                if final_url != PUBLIC_MEMBERSHIP_JOIN_URL:
                    raise base.NoteDraftError(f"Run339b refuses unexpected post-hydration final URL: {final_url!r}")

                page_title = _canon(page.title())
                challenge_hits = [m for m in run326.BOT_OR_CHALLENGE_MARKERS if m.lower() in body_text.lower()]
                if challenge_hits:
                    raise base.NoteDraftError(f"Run339b membership page is blocked by challenge: {challenge_hits}")

                not_available_hits = [m for m in run337.NOT_AVAILABLE_MARKERS if m in body_text]
                if not_available_hits:
                    raise base.NoteDraftError(f"Run339b membership page reports unavailable state: {not_available_hits}")

                membership_verified = run333.MEMBERSHIP_NAME in body_text
                current_description = _canon(run333.NEW_DESCRIPTION)
                legacy_description = _canon(run333.OLD_DESCRIPTION)
                description_verified = current_description in body_text
                legacy_description_absent = legacy_description not in body_text and _canon(run332.LEGACY_REFERENCE) not in body_text
                price_verified = run337._price_verified(body_text)
                stale_profile_absent = _canon(run311.LEGACY_PROFILE) not in body_text
                current_profile_visible = _canon(run311.CURRENT_PROFILE) in body_text
                joins = run337._join_candidates(actions)
                logged_out_ui_verified = _logged_out_ui_verified(actions)
                benefits_verified = all(value in body_text for value in EXPECTED_BENEFITS)
                onboarding_link_verified = _exact_onboarding_link_verified(page, body_text)

                if not all((membership_verified, description_verified, legacy_description_absent, price_verified)):
                    raise base.NoteDraftError("Run339b core purchase-surface contract is incomplete after hydration")
                if not stale_profile_absent or not current_profile_visible:
                    raise base.NoteDraftError("Run339b public purchase surface profile biography is not current")
                if not joins:
                    raise base.NoteDraftError("Run339b could not identify a visible join/signup action")
                if not logged_out_ui_verified:
                    raise base.NoteDraftError("Run339b could not positively verify logged-out UI")
                if not benefits_verified:
                    raise base.NoteDraftError("Run339b public purchase surface is missing an expected paid benefit")
                if not onboarding_link_verified:
                    raise base.NoteDraftError("Run339b could not verify the exact current onboarding article link")

                cookies_after = context.cookies()
                note_cookie_names_after = sorted(
                    {
                        str(item.get("name") or "")
                        for item in cookies_after
                        if str(item.get("domain") or "").endswith("note.com")
                    }
                )
                explicit_auth_cookie_names = _explicit_auth_cookie_names(
                    note_cookie_names_after, logged_out_ui_verified
                )
                if explicit_auth_cookie_names:
                    raise base.NoteDraftError(
                        f"Run339b fresh logged-out context acquired unexpected auth-like cookies: {explicit_auth_cookie_names}"
                    )

                screenshot_file = os.environ.get(SCREENSHOT_ENV, "").strip()
                if screenshot_file:
                    path = Path(screenshot_file)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(path), full_page=True)

                return {
                    "status": "logged_out_membership_purchase_surface_verified",
                    "run": "Run339b",
                    "public_url": PUBLIC_MEMBERSHIP_URL,
                    "initial_url": initial_url,
                    "final_url": final_url,
                    "redirect_to_join_verified": True,
                    "http_status": http_status,
                    "page_title": page_title,
                    "hydration_wait_ms": hydration_wait_ms,
                    "membership_name_verified": membership_verified,
                    "price_1980_month_verified": price_verified,
                    "current_description_verified": description_verified,
                    "legacy_description_absent": legacy_description_absent,
                    "stale_profile_absent": stale_profile_absent,
                    "current_profile_visible": current_profile_visible,
                    "benefits_verified": benefits_verified,
                    "onboarding_link_verified": onboarding_link_verified,
                    "join_action_verified": True,
                    "join_candidates": joins[:12],
                    "logged_out_ui_verified": logged_out_ui_verified,
                    "not_available_hits": not_available_hits,
                    "cookies_before_navigation": [],
                    "note_cookie_names_after": note_cookie_names_after,
                    "anonymous_note_session_seen": run326.ANONYMOUS_NOTE_SESSION_COOKIE in note_cookie_names_after,
                    "anonymous_note_gql_auth_token_seen": ANONYMOUS_LOGGED_OUT_AUTHLIKE_COOKIE in note_cookie_names_after,
                    "explicit_auth_cookie_names_after": explicit_auth_cookie_names,
                    "fresh_no_cookie_context": True,
                    "body_visible_chars": len(body_text),
                    "body_excerpt": body_text[:10000],
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
    print("RUN339B_MEMBERSHIP_PUBLIC_FUNNEL_AUDIT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
