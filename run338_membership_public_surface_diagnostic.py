#!/usr/bin/env python3
"""Run338: zero-click diagnostic for the logged-out note membership customer surface.

Run337 failed closed because the initial public membership DOM did not expose the expected
membership name. Run338 does not weaken that customer contract and does not mutate note. Instead,
it records enough evidence to distinguish a real public-funnel defect from delayed/client-side
rendering, route-shell behavior, or a changed note public URL.

Safety contract:
- fresh browser with zero seeded cookies/storage;
- direct navigation only to the exact public membership page and exact public creator page;
- no clicks, fills, keyboard input, submissions, editor/settings routes, or note mutations;
- capture multiple DOM checkpoints, raw HTML markers, visible actions/links, network/console errors,
  and screenshots before classifying the observed public state;
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
import run332_membership_description_edit_route_probe as run332
import run333_membership_description_exact_update as run333
import run337_membership_public_funnel_audit as run337

CONFIRM_TOKEN = "DIAGNOSE_PUBLIC_MEMBERSHIP_TRENDHUB_BIZ_RUN338_LOGGED_OUT"
RESULT_ENV = "NOTE_MEMBERSHIP_PUBLIC_RUN338_RESULT_FILE"
MEMBERSHIP_SCREENSHOT_ENV = "NOTE_MEMBERSHIP_PUBLIC_RUN338_MEMBERSHIP_SCREENSHOT_FILE"
PROFILE_SCREENSHOT_ENV = "NOTE_MEMBERSHIP_PUBLIC_RUN338_PROFILE_SCREENSHOT_FILE"
PUBLIC_MEMBERSHIP_URL = run337.PUBLIC_MEMBERSHIP_URL
PUBLIC_PROFILE_URL = run311.PUBLIC_PROFILE_URL
CHECKPOINT_DELAYS_MS = (0, 1500, 2500, 4000)  # cumulative: 0s, 1.5s, 4.0s, 8.0s


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


def _visible_actions(page: Any, limit: int = 80) -> list[dict[str, str]]:
    rows = page.locator("button:visible, a:visible")
    out: list[dict[str, str]] = []
    for idx in range(min(rows.count(), limit)):
        item = rows.nth(idx)
        try:
            out.append(
                {
                    "tag": _canon(item.evaluate("el => el.tagName.toLowerCase()")),
                    "text": _canon(item.inner_text(timeout=2500))[:500],
                    "ariaLabel": _canon(item.get_attribute("aria-label"))[:500],
                    "href": str(item.get_attribute("href") or "").strip()[:1500],
                }
            )
        except Exception:
            continue
    return out


def _membership_links(page: Any, limit: int = 80) -> list[dict[str, str]]:
    rows = page.locator("a[href]")
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for idx in range(min(rows.count(), 500)):
        item = rows.nth(idx)
        try:
            href = str(item.get_attribute("href") or "").strip()
            text = _canon(item.inner_text(timeout=1500))[:500]
        except Exception:
            continue
        if "membership" not in href.lower() and "メンバーシップ" not in text:
            continue
        key = (href, text)
        if key in seen:
            continue
        seen.add(key)
        out.append({"href": href[:1500], "text": text})
        if len(out) >= limit:
            break
    return out


def _marker_state(text: str, html: str) -> dict[str, Any]:
    body = _canon(text)
    raw = str(html or "")
    current_description = _canon(run333.NEW_DESCRIPTION)
    legacy_description = _canon(run333.OLD_DESCRIPTION)
    legacy_reference = _canon(run332.LEGACY_REFERENCE)
    return {
        "membership_name_in_body": run333.MEMBERSHIP_NAME in body,
        "membership_name_in_html": run333.MEMBERSHIP_NAME in raw,
        "current_description_in_body": current_description in body,
        "current_description_in_html": current_description in raw,
        "legacy_description_in_body": legacy_description in body,
        "legacy_reference_in_body": legacy_reference in body,
        "price_in_body": run337._price_verified(body),
        "stale_profile_in_body": _canon(run311.LEGACY_PROFILE) in body,
        "current_profile_in_body": _canon(run311.CURRENT_PROFILE) in body,
        "not_available_hits": [m for m in run337.NOT_AVAILABLE_MARKERS if m in body],
        "challenge_hits": [m for m in run326.BOT_OR_CHALLENGE_MARKERS if m.lower() in body.lower()],
    }


def _checkpoint(page: Any, label: str) -> dict[str, Any]:
    body_text = _canon(page.locator("body").inner_text(timeout=10000))
    html = page.content()
    actions = _visible_actions(page)
    return {
        "label": label,
        "url": str(page.url or ""),
        "title": _canon(page.title()),
        "ready_state": str(page.evaluate("document.readyState") or ""),
        "body_chars": len(body_text),
        "html_chars": len(html),
        "body_excerpt": body_text[:12000],
        "html_excerpt": html[:12000],
        "meta_description": _meta_content(page, 'meta[name="description"]'),
        "og_title": _meta_content(page, 'meta[property="og:title"]'),
        "og_description": _meta_content(page, 'meta[property="og:description"]'),
        "markers": _marker_state(body_text, html),
        "visible_actions": actions[:40],
        "join_candidates": run337._join_candidates(actions)[:20],
        "membership_links": _membership_links(page)[:30],
    }


def _classify(membership_checkpoints: list[dict[str, Any]], profile_links: list[dict[str, str]]) -> str:
    if not membership_checkpoints:
        return "no_membership_observation"
    final = membership_checkpoints[-1]
    markers = final.get("markers") or {}
    if markers.get("challenge_hits"):
        return "challenge_or_blocked"
    if markers.get("not_available_hits"):
        return "membership_unavailable_publicly"
    if (
        markers.get("membership_name_in_body")
        and markers.get("current_description_in_body")
        and markers.get("price_in_body")
        and final.get("join_candidates")
    ):
        return "public_purchase_surface_current"
    if markers.get("membership_name_in_html") and not markers.get("membership_name_in_body"):
        return "membership_data_present_but_not_visible"
    if profile_links and not markers.get("membership_name_in_body"):
        return "profile_links_membership_but_target_surface_missing_expected_content"
    return "public_surface_missing_expected_membership_content"


def diagnose() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBERSHIP_PUBLIC_RUN338_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run338 exact diagnostic confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run338") from exc

    result: dict[str, Any] = {
        "status": "diagnostic_completed_no_mutation",
        "public_membership_url": PUBLIC_MEMBERSHIP_URL,
        "public_profile_url": PUBLIC_PROFILE_URL,
        "membership_checkpoints": [],
        "profile_membership_links": [],
        "request_failures": [],
        "http_error_responses": [],
        "console_errors": [],
        "page_errors": [],
        "cookies_before_navigation": [],
        "note_cookie_names_after": [],
        "explicit_auth_cookie_names_after": [],
        "fresh_no_cookie_context": False,
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

    with sync_playwright() as playwright:
        browser = run317._launch_clean_browser(playwright)
        try:
            context = browser.new_context(
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                viewport={"width": 1440, "height": 1200},
            )
            try:
                before = context.cookies()
                result["cookies_before_navigation"] = before
                if before:
                    result["classification"] = "unexpected_seeded_cookie_state"
                    return result
                result["fresh_no_cookie_context"] = True

                page = context.new_page()
                page.set_default_timeout(30000)

                def on_request_failed(request: Any) -> None:
                    try:
                        failure = request.failure
                        result["request_failures"].append(
                            {"url": str(request.url)[:1800], "method": str(request.method), "failure": str(failure)[:1000]}
                        )
                    except Exception:
                        pass

                def on_response(response: Any) -> None:
                    try:
                        if int(response.status) >= 400:
                            result["http_error_responses"].append(
                                {"status": int(response.status), "url": str(response.url)[:1800]}
                            )
                    except Exception:
                        pass

                def on_console(message: Any) -> None:
                    try:
                        if str(message.type).lower() == "error":
                            result["console_errors"].append(_canon(message.text)[:2000])
                    except Exception:
                        pass

                page.on("requestfailed", on_request_failed)
                page.on("response", on_response)
                page.on("console", on_console)
                page.on("pageerror", lambda error: result["page_errors"].append(_canon(error)[:2000]))

                try:
                    response = page.goto(PUBLIC_MEMBERSHIP_URL, wait_until="domcontentloaded", timeout=60000)
                    result["membership_http_status"] = response.status if response is not None else None
                except Exception as exc:
                    result["membership_navigation_error"] = f"{type(exc).__name__}: {exc}"[:3000]

                for idx, delay_ms in enumerate(CHECKPOINT_DELAYS_MS):
                    if delay_ms:
                        page.wait_for_timeout(delay_ms)
                    try:
                        result["membership_checkpoints"].append(_checkpoint(page, f"t{(sum(CHECKPOINT_DELAYS_MS[:idx+1])/1000):.1f}s"))
                    except Exception as exc:
                        result.setdefault("checkpoint_errors", []).append(
                            {"index": idx, "error": f"{type(exc).__name__}: {exc}"[:3000]}
                        )

                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                    result["networkidle_reached"] = True
                except Exception as exc:
                    result["networkidle_reached"] = False
                    result["networkidle_error"] = f"{type(exc).__name__}: {exc}"[:2000]

                try:
                    final_checkpoint = _checkpoint(page, "post-networkidle-attempt")
                    result["membership_checkpoints"].append(final_checkpoint)
                except Exception as exc:
                    result.setdefault("checkpoint_errors", []).append(
                        {"index": "networkidle", "error": f"{type(exc).__name__}: {exc}"[:3000]}
                    )

                membership_screenshot = os.environ.get(MEMBERSHIP_SCREENSHOT_ENV, "").strip()
                if membership_screenshot:
                    try:
                        path = Path(membership_screenshot)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(path), full_page=True)
                        result["membership_screenshot_written"] = True
                    except Exception as exc:
                        result["membership_screenshot_written"] = False
                        result["membership_screenshot_error"] = f"{type(exc).__name__}: {exc}"[:2000]

                # Direct navigation only: discover the public membership href note exposes from the creator page.
                try:
                    profile_response = page.goto(PUBLIC_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
                    result["profile_http_status"] = profile_response.status if profile_response is not None else None
                    page.wait_for_timeout(3500)
                    result["profile_final_url"] = str(page.url or "")
                    result["profile_title"] = _canon(page.title())
                    result["profile_body_excerpt"] = _canon(page.locator("body").inner_text(timeout=10000))[:12000]
                    result["profile_membership_links"] = _membership_links(page)[:50]
                    result["profile_visible_actions"] = _visible_actions(page)[:50]
                except Exception as exc:
                    result["profile_navigation_error"] = f"{type(exc).__name__}: {exc}"[:3000]

                profile_screenshot = os.environ.get(PROFILE_SCREENSHOT_ENV, "").strip()
                if profile_screenshot:
                    try:
                        path = Path(profile_screenshot)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(path), full_page=True)
                        result["profile_screenshot_written"] = True
                    except Exception as exc:
                        result["profile_screenshot_written"] = False
                        result["profile_screenshot_error"] = f"{type(exc).__name__}: {exc}"[:2000]

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
                result["note_cookie_names_after"] = note_cookie_names_after
                result["explicit_auth_cookie_names_after"] = explicit_auth_cookie_names
                result["anonymous_note_session_seen"] = run326.ANONYMOUS_NOTE_SESSION_COOKIE in note_cookie_names_after
                result["classification"] = _classify(
                    result.get("membership_checkpoints") or [], result.get("profile_membership_links") or []
                )
                return result
            finally:
                context.close()
        finally:
            browser.close()


def main() -> None:
    output = os.environ.get(RESULT_ENV, "").strip()
    try:
        result = diagnose()
    except Exception as exc:
        result = {
            "status": "diagnostic_runtime_error_no_mutation",
            "error": f"{type(exc).__name__}: {exc}"[:5000],
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
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN338_MEMBERSHIP_PUBLIC_SURFACE_DIAGNOSTIC=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
