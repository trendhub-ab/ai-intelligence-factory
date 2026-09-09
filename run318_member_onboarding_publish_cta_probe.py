#!/usr/bin/env python3
"""Run318: clean-context, no-mutation probe of the exact onboarding publish CTA.

Run317 proved the rewritten onboarding article is now persisted on note's server. Run318 opens
that exact server-saved revision in a clean cookie-only browser, enters publish settings, and
inventories the current actionable controls without changing membership/settings or clicking any
final update/publish control.

ZERO model calls, ZERO Notion writes, ZERO public mutation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run310_public_lp_update as run310
import run315_member_onboarding_update as run315
import run316_member_onboarding_finalize_probe as run316
import run317_member_onboarding_server_save as run317

CONFIRM_TOKEN = "PROBE_MEMBER_ONBOARDING_PUBLISH_CTA_N284E428C80F4_SHAAAB9E57B"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_PUBLISH_CTA_PROBE_RESULT_FILE"


def _cookie_source(playwright: Any) -> list[dict[str, Any]]:
    persistent = cloud._launch_persistent_context(playwright)
    try:
        pages = list(persistent.pages)
        page = pages[0] if pages else persistent.new_page()
        page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(700)
        cookies = run317._note_cookies(persistent.cookies())
        if not cookies:
            raise base.NoteAuthenticationExpired("Run318 persistent note session has no authentication cookies")
        return cookies
    finally:
        persistent.close()


def _candidate_commit_controls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = ("更新する", "更新", "公開する", "公開", "投稿する", "投稿", "保存する", "保存")
    out: list[dict[str, Any]] = []
    for row in rows:
        text = str(row.get("text") or "").strip()
        aria = str(row.get("ariaLabel") or "").strip()
        title = str(row.get("title") or "").strip()
        if any(value in labels for value in (text, aria, title)):
            out.append(row)
    return out


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_PUBLISH_CTA_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run318 exact publish-CTA probe confirmation is missing or invalid")

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run318") from exc

    with sync_playwright() as playwright:
        cookies = _cookie_source(playwright)
        browser = run317._launch_clean_browser(playwright)
        try:
            context = run317._new_cookie_only_context(browser, cookies)
            try:
                page = context.new_page()
                page.set_default_timeout(30000)
                title_field, body, title, body_text = run317._open_exact_clean_editor(page)
                body_sha = run315._sha256(body_text)
                if title != run315.NEW_TITLE or body_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run318 refuses non-server-saved source state: title={title!r} sha256={body_sha}"
                    )
                run315._verify_editor(body)

                run310._unique_button(page, "公開に進む").click()
                try:
                    page.wait_for_url(f"**/notes/{run315.TARGET_NOTE_ID}/publish/**", timeout=15000)
                except PlaywrightTimeoutError as exc:
                    raise base.NoteDraftError("Run318 did not reach exact onboarding publish settings") from exc
                if not str(page.url or "").startswith(run315.TARGET_PUBLISH_URL):
                    raise base.NoteDraftError("Run318 publish URL is not the exact onboarding note")
                page.wait_for_timeout(1200)

                settings_text = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
                if "記事タイプ" not in settings_text or "無料" not in settings_text or run315.MEMBERSHIP_NAME not in settings_text:
                    raise base.NoteDraftError("Run318 publish settings do not match the exact free onboarding article")

                controls = run316._control_inventory(page)
                candidates = _candidate_commit_controls(controls)
                raw_markers = {
                    marker: settings_text.count(marker)
                    for marker in ("更新する", "更新", "公開する", "投稿する", "投稿", "保存する")
                }

                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(400)
                controls_bottom = run316._control_inventory(page)
                candidates_bottom = _candidate_commit_controls(controls_bottom)

                return {
                    "status": "probe_complete_no_mutation",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": title,
                    "source_body_sha256": body_sha,
                    "fresh_cookie_only_context": True,
                    "local_storage_seeded": False,
                    "publish_url": str(page.url or ""),
                    "controls": controls,
                    "candidate_commit_controls": candidates,
                    "controls_after_bottom_scroll": controls_bottom,
                    "candidate_commit_controls_after_bottom_scroll": candidates_bottom,
                    "raw_commit_marker_counts": raw_markers,
                    "publish_settings_text": settings_text[:18000],
                    "final_commit_clicked": False,
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
    result = probe()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN318_MEMBER_ONBOARDING_PUBLISH_CTA_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
