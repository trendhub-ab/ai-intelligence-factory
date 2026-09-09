#!/usr/bin/env python3
"""Run322: select the exact latest draft, confirm 編集する, then probe publish settings.

Run321b proved note's existing-article `編集` route is two-stage when an unpublished revision
exists: select `最新の下書き`, then click `編集する`. Run322 follows exactly that observed route,
re-verifies the exact Run317 server-saved title/body, enters `公開に進む`, inventories the final
publish-settings controls, and stops before any save/update/publish action.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run310_public_lp_update as run310
import run315_member_onboarding_update as run315
import run316_member_onboarding_finalize_probe as run316
import run317_member_onboarding_server_save as run317
import run318_member_onboarding_publish_cta_probe as run318
import run319_member_onboarding_article_list_probe as run319
import run321_member_onboarding_official_edit_route_probe as run321

CONFIRM_TOKEN = run321.CONFIRM_TOKEN
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_VERSION_CONFIRM_PUBLISH_PROBE_RESULT_FILE"
EDIT_CONFIRM_LABEL = "編集する"


def _exact_visible_text(page: Any, label: str) -> Any:
    loc = page.get_by_text(label, exact=True)
    visible: list[Any] = []
    for idx in range(loc.count()):
        item = loc.nth(idx)
        try:
            if item.is_visible():
                visible.append(item)
        except Exception:
            pass
    if len(visible) != 1:
        raise base.NoteDraftError(f"Run322 expected one exact visible text {label!r}; got {len(visible)}")
    return visible[0]


def _select_latest_and_confirm(page: Any) -> dict[str, Any]:
    dialog = page.locator('[role="dialog"]')
    visible_dialogs: list[Any] = []
    for idx in range(dialog.count()):
        item = dialog.nth(idx)
        try:
            if item.is_visible():
                visible_dialogs.append(item)
        except Exception:
            pass
    if len(visible_dialogs) != 1:
        raise base.NoteDraftError(f"Run322 expected one exact version dialog; got {len(visible_dialogs)}")
    text = " ".join(str(visible_dialogs[0].inner_text() or "").split())
    required = (
        "公開されていない下書きがあります",
        "どちらを編集しますか？",
        "公開した時点の記事",
        run321.LATEST_DRAFT_LABEL,
        "キャンセル",
        EDIT_CONFIRM_LABEL,
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise base.NoteDraftError(f"Run322 version dialog contract drifted; missing={missing}")

    _exact_visible_text(page, run321.LATEST_DRAFT_LABEL).click()
    page.wait_for_timeout(250)
    run321._visible_exact(page, role="button", name=EDIT_CONFIRM_LABEL).click()
    try:
        page.wait_for_url(f"**/notes/{run315.TARGET_NOTE_ID}/edit/**", timeout=15000)
    except Exception as exc:
        raise base.NoteDraftError(f"Run322 編集する did not reach exact editor: {page.url}") from exc
    if not run315._is_exact_editor(str(page.url or "")):
        raise base.NoteDraftError(f"Run322 editor URL drifted from exact target: {page.url}")
    return {
        "dialog_text": text,
        "latest_draft_selected": True,
        "edit_confirm_clicked": True,
        "editor_url": str(page.url or ""),
    }


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_VERSION_CONFIRM_PUBLISH_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run322 exact version-confirm publish probe confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run322") from exc

    with sync_playwright() as playwright:
        cookies = run318._cookie_source(playwright)
        browser = run317._launch_clean_browser(playwright)
        try:
            context = run317._new_cookie_only_context(browser, cookies)
            try:
                page = context.new_page()
                page.set_default_timeout(30000)

                # Exact clean server-state proof before using any article-list navigation.
                _, body, source_title, source_body_text = run317._open_exact_clean_editor(page)
                source_sha = run315._sha256(source_body_text)
                if source_title != run315.NEW_TITLE or source_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run322 refuses non-server-saved source state: title={source_title!r} sha256={source_sha}"
                    )
                run315._verify_editor(body)

                page.goto(run319.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1600)
                card = run319._mark_target_card(page)
                if not card.get("cardFound"):
                    raise base.NoteDraftError("Run322 exact target article card was not found")
                menu = run319._open_menu_if_exact(page, card)
                if not menu.get("opened"):
                    raise base.NoteDraftError(f"Run322 exact target menu did not open: {menu}")
                run321._visible_exact(page, role="menuitem", name=run321.EDIT_LABEL).click()
                page.wait_for_timeout(700)

                version_route = _select_latest_and_confirm(page)
                page.wait_for_timeout(800)
                title_field = base._find_title(page)
                body = base._find_body(page, title_field)
                routed_title = run315._field_text(title_field)
                routed_body_text = run315._body_text(body)
                routed_sha = run315._sha256(routed_body_text)
                if routed_title != run315.NEW_TITLE or routed_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run322 latest-draft route exposed wrong revision: title={routed_title!r} sha256={routed_sha}"
                    )
                run315._verify_editor(body)
                editor_snapshot = run321._snapshot(page)

                run310._unique_button(page, "公開に進む").click()
                try:
                    page.wait_for_url(f"**/notes/{run315.TARGET_NOTE_ID}/publish/**", timeout=15000)
                except Exception as exc:
                    raise base.NoteDraftError("Run322 official latest-draft route did not reach exact publish settings") from exc
                if not str(page.url or "").startswith(run315.TARGET_PUBLISH_URL):
                    raise base.NoteDraftError(f"Run322 publish-settings URL drifted: {page.url}")
                page.wait_for_timeout(1200)

                publish_snapshot = run321._snapshot(page)
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(500)
                publish_bottom_snapshot = run321._snapshot(page)
                rows = publish_snapshot["all_actionables"] + publish_bottom_snapshot["all_actionables"]
                commit_candidates = run321._commit_candidates(rows)
                membership_visible = run315.MEMBERSHIP_NAME in str(publish_snapshot.get("body_text") or "") or run315.MEMBERSHIP_NAME in str(publish_bottom_snapshot.get("body_text") or "")

                return {
                    "status": "probe_complete_no_public_mutation",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": source_title,
                    "source_body_sha256": source_sha,
                    "fresh_cookie_only_context": True,
                    "local_storage_seeded": False,
                    "article_list_card": card,
                    "article_list_menu": menu,
                    "edit_menu_clicked": True,
                    "version_route": version_route,
                    "routed_title": routed_title,
                    "routed_body_sha256": routed_sha,
                    "editor_snapshot": editor_snapshot,
                    "publish_snapshot": publish_snapshot,
                    "publish_bottom_snapshot": publish_bottom_snapshot,
                    "candidate_commit_controls": commit_candidates,
                    "membership_name_visible": membership_visible,
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
    print("RUN322_MEMBER_ONBOARDING_VERSION_CONFIRM_PUBLISH_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
