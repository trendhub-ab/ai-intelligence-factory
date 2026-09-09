#!/usr/bin/env python3
"""Run324: open the membership trial-read surface without committing anything.

Run323 proved the exact existing-article latest-draft route reaches note's publish settings for
n284e428c80f4, but that surface has no `更新する` control and instead exposes the exact
`試し読みエリアを設定` CTA. note's current help documents trial-read setup as the intermediate
step for membership-benefit/free content and says an already-published article exposes `更新する`
after entering that setup flow. Run324 clicks only that intermediate CTA, inventories the resulting
surface, and stops before choosing a trial-read line or clicking any save/update/publish control.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run310_public_lp_update as run310
import run315_member_onboarding_update as run315
import run317_member_onboarding_server_save as run317
import run318_member_onboarding_publish_cta_probe as run318
import run319_member_onboarding_article_list_probe as run319
import run321_member_onboarding_official_edit_route_probe as run321
import run322_member_onboarding_version_confirm_publish_probe as run322
import run323_member_onboarding_publish_surface_deep_probe as run323

CONFIRM_TOKEN = "PROBE_MEMBER_ONBOARDING_TRIAL_READ_SURFACE_N284E428C80F4_SHAAAB9E57B"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_TRIAL_READ_SURFACE_PROBE_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_MEMBER_ONBOARDING_TRIAL_READ_SURFACE_PROBE_SCREENSHOT_FILE"
TRIAL_READ_LABEL = "試し読みエリアを設定"
FINAL_UPDATE_LABEL = "更新する"
LINE_LABEL_FRAGMENT = "ラインをこの場所に変更"


def _canon(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _visible_button_texts(page: Any) -> list[str]:
    return [_canon(value) for value in page.locator("button:visible").all_text_contents() if _canon(value)]


def _visible_exact_button_count(page: Any, label: str) -> int:
    return sum(1 for value in _visible_button_texts(page) if value == label)


def _line_candidate_count(page: Any) -> int:
    return sum(1 for value in _visible_button_texts(page) if LINE_LABEL_FRAGMENT in value)


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_TRIAL_READ_SURFACE_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run324 exact trial-read-surface confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run324") from exc

    with sync_playwright() as playwright:
        cookies = run318._cookie_source(playwright)
        browser = run317._launch_clean_browser(playwright)
        try:
            context = run317._new_cookie_only_context(browser, cookies)
            try:
                page = context.new_page()
                page.set_default_timeout(30000)
                try:
                    page.set_viewport_size({"width": 1440, "height": 1200})
                except Exception:
                    pass

                # Re-prove the exact server-saved latest draft before navigating away.
                _, body, source_title, source_body_text = run317._open_exact_clean_editor(page)
                source_sha = run315._sha256(source_body_text)
                if source_title != run315.NEW_TITLE or source_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run324 refuses non-server-saved source state: title={source_title!r} sha256={source_sha}"
                    )
                run315._verify_editor(body)

                # Use the Run321b/322 proven existing-article route and explicitly choose the latest draft.
                page.goto(run319.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1600)
                card = run319._mark_target_card(page)
                if not card.get("cardFound"):
                    raise base.NoteDraftError("Run324 exact target article card was not found")
                menu = run319._open_menu_if_exact(page, card)
                if not menu.get("opened"):
                    raise base.NoteDraftError(f"Run324 exact target menu did not open: {menu}")
                run321._visible_exact(page, role="menuitem", name=run321.EDIT_LABEL).click()
                page.wait_for_timeout(700)
                version_route = run322._select_latest_and_confirm(page)
                page.wait_for_timeout(700)

                title_field = base._find_title(page)
                body = base._find_body(page, title_field)
                routed_title = run315._field_text(title_field)
                routed_body_text = run315._body_text(body)
                routed_sha = run315._sha256(routed_body_text)
                if routed_title != run315.NEW_TITLE or routed_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run324 routed revision mismatch: title={routed_title!r} sha256={routed_sha}"
                    )
                run315._verify_editor(body)

                run310._unique_button(page, "公開に進む").click()
                try:
                    page.wait_for_url(f"**/notes/{run315.TARGET_NOTE_ID}/publish/**", timeout=15000)
                except Exception as exc:
                    raise base.NoteDraftError("Run324 did not reach exact publish settings") from exc
                if not str(page.url or "").startswith(run315.TARGET_PUBLISH_URL):
                    raise base.NoteDraftError(f"Run324 publish URL drifted: {page.url}")
                page.wait_for_timeout(1200)

                publish_surface = run323._deep_surface(page, "publish_settings_before_trial_read")
                pre_buttons = _visible_button_texts(page)
                pre_update_count = _visible_exact_button_count(page, FINAL_UPDATE_LABEL)
                pre_trial_count = _visible_exact_button_count(page, TRIAL_READ_LABEL)
                if pre_update_count != 0:
                    raise base.NoteDraftError(
                        f"Run324 expected Run323 missing-update precondition; visible {FINAL_UPDATE_LABEL}={pre_update_count}"
                    )
                if pre_trial_count != 1:
                    raise base.NoteDraftError(
                        f"Run324 expected exactly one visible {TRIAL_READ_LABEL}; observed={pre_trial_count}"
                    )

                # This is the sole interaction under Run324. It opens the documented intermediate
                # trial-read surface; no line selection and no final commit are allowed below.
                run310._unique_button(page, TRIAL_READ_LABEL).click()
                page.wait_for_timeout(900)
                after_t1 = run323._deep_surface(page, "trial_read_after_t1")
                page.wait_for_timeout(1800)
                after_t3 = run323._deep_surface(page, "trial_read_after_t3")
                try:
                    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                    page.wait_for_timeout(800)
                except Exception:
                    pass
                after_bottom = run323._deep_surface(page, "trial_read_bottom")

                post_buttons = _visible_button_texts(page)
                post_update_count = _visible_exact_button_count(page, FINAL_UPDATE_LABEL)
                line_candidate_count = _line_candidate_count(page)
                post_url = str(page.url or "")

                screenshot_file = os.environ.get(SCREENSHOT_ENV, "").strip()
                if screenshot_file:
                    path = Path(screenshot_file)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(path), full_page=True)

                snapshots = [publish_surface, after_t1, after_t3, after_bottom]
                candidate_labels: list[str] = []
                for snap in snapshots:
                    for label in run323._candidate_labels(snap):
                        if label not in candidate_labels:
                            candidate_labels.append(label)

                return {
                    "status": "trial_read_surface_probe_complete_no_public_mutation",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": source_title,
                    "source_body_sha256": source_sha,
                    "routed_title": routed_title,
                    "routed_body_sha256": routed_sha,
                    "version_route": version_route,
                    "publish_url_before_trial_read": run315.TARGET_PUBLISH_URL,
                    "url_after_trial_read": post_url,
                    "pre_visible_buttons": pre_buttons,
                    "post_visible_buttons": post_buttons,
                    "pre_exact_update_count": pre_update_count,
                    "pre_exact_trial_read_count": pre_trial_count,
                    "post_exact_update_count": post_update_count,
                    "trial_read_line_candidate_count": line_candidate_count,
                    "snapshots": snapshots,
                    "candidate_labels": candidate_labels[:200],
                    "screenshot_written": bool(screenshot_file),
                    "trial_read_cta_clicked": True,
                    "trial_read_line_clicked": False,
                    "final_commit_clicked": False,
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
    result = probe()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN324_MEMBER_ONBOARDING_TRIAL_READ_SURFACE_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
