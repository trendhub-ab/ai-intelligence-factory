#!/usr/bin/env python3
"""Run321b: diagnose the exact UI shown after the existing-article `編集` menu action.

Run321 proved the exact menu item can be clicked, but note remained on `/notes` instead of
navigating to the editor. This diagnostic captures that intermediate UI without guessing a next
control. It never edits content, enters publish settings, changes membership, or publishes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run315_member_onboarding_update as run315
import run317_member_onboarding_server_save as run317
import run318_member_onboarding_publish_cta_probe as run318
import run319_member_onboarding_article_list_probe as run319
import run321_member_onboarding_official_edit_route_probe as run321

CONFIRM_TOKEN = "DIAG_MEMBER_ONBOARDING_EDIT_ROUTE_N284E428C80F4_SHAAAB9E57B"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_EDIT_ROUTE_DIAGNOSTIC_RESULT_FILE"


def _exact_visible_texts(page: Any, labels: tuple[str, ...]) -> dict[str, int]:
    out: dict[str, int] = {}
    for label in labels:
        loc = page.get_by_text(label, exact=True)
        count = 0
        for idx in range(loc.count()):
            try:
                if loc.nth(idx).is_visible():
                    count += 1
            except Exception:
                pass
        out[label] = count
    return out


def diagnose() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_EDIT_ROUTE_DIAGNOSTIC_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run321b exact edit-route diagnostic confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run321b") from exc

    with sync_playwright() as playwright:
        cookies = run318._cookie_source(playwright)
        browser = run317._launch_clean_browser(playwright)
        try:
            context = run317._new_cookie_only_context(browser, cookies)
            try:
                page = context.new_page()
                page.set_default_timeout(30000)

                # Re-prove the exact server-saved latest draft before using the article list.
                _, body, title, body_text = run317._open_exact_clean_editor(page)
                body_sha = run315._sha256(body_text)
                if title != run315.NEW_TITLE or body_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run321b refuses non-server-saved source state: title={title!r} sha256={body_sha}"
                    )
                run315._verify_editor(body)

                page.goto(run319.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1600)
                card = run319._mark_target_card(page)
                if not card.get("cardFound"):
                    raise base.NoteDraftError("Run321b exact target article card was not found")
                menu = run319._open_menu_if_exact(page, card)
                if not menu.get("opened"):
                    raise base.NoteDraftError(f"Run321b exact target menu did not open: {menu}")

                run321._visible_exact(page, role="menuitem", name=run321.EDIT_LABEL).click()
                page.wait_for_timeout(1500)
                after_edit = run321._snapshot(page)
                exact_labels_after_edit = _exact_visible_texts(
                    page,
                    (
                        "最新の下書き",
                        "公開した時点の記事",
                        "下書きを編集",
                        "公開中の記事を編集",
                        "編集する",
                        "キャンセル",
                        "閉じる",
                    ),
                )

                # Use only the already-authorized exact latest-draft navigation helper. If its
                # exact labels are absent, it performs no click and we simply record the UI.
                version_choice = run321._maybe_choose_latest_draft(page)
                if version_choice.get("latest_choice_clicked"):
                    page.wait_for_timeout(1000)
                after_version_choice = run321._snapshot(page)

                return {
                    "status": "diagnostic_complete_no_mutation",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": title,
                    "source_body_sha256": body_sha,
                    "fresh_cookie_only_context": True,
                    "local_storage_seeded": False,
                    "article_list_card": card,
                    "article_list_menu": menu,
                    "edit_menu_clicked": True,
                    "after_edit": after_edit,
                    "exact_labels_after_edit": exact_labels_after_edit,
                    "version_choice": version_choice,
                    "after_version_choice": after_version_choice,
                    "editor_route_reached": run315._is_exact_editor(str(page.url or "")),
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
    result = diagnose()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN321B_MEMBER_ONBOARDING_EDIT_ROUTE_DIAGNOSTIC=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
