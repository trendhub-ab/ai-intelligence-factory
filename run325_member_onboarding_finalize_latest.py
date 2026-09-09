#!/usr/bin/env python3
"""Run325: finalize the exact server-saved onboarding draft through note's proven trial-read bridge.

Run324 proved that for the already-published free membership-benefit article n284e428c80f4,
`更新する` is intentionally absent from the ordinary publish-settings surface and appears only
after opening `試し読みエリアを設定`. The current article is already attached to the
`AI Decision Intelligence` plan, and Run320 proved that with no trial-read line the full article
is limited to plan members.

Run325 therefore performs one hard-bound public maintenance action only:
- re-prove the exact latest draft title/body SHA;
- use the existing-article edit route and select the latest draft;
- open publish settings;
- open trial-read setup;
- select NO trial-read line (preserving full members-only access);
- click the single exact `更新する` once;
- prove the article-list card now exposes the new title with no unpublished-draft marker;
- re-open the membership dialog read-only and prove `AI Decision Intelligence` remains `追加済`.

No model calls, no Notion writes, no membership selection, and no other account/article setting
is changed.
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
import run320_member_onboarding_membership_dialog_probe as run320
import run321_member_onboarding_official_edit_route_probe as run321
import run322_member_onboarding_version_confirm_publish_probe as run322
import run324_member_onboarding_trial_read_surface_probe as run324

CONFIRM_TOKEN = "FINALIZE_MEMBER_ONBOARDING_N284E428C80F4_SHAAAB9E57B_KEEP_MEMBERS_ONLY"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_FINALIZE_LATEST_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_MEMBER_ONBOARDING_FINALIZE_LATEST_SCREENSHOT_FILE"
TRIAL_READ_LABEL = "試し読みエリアを設定"
FINAL_UPDATE_LABEL = "更新する"
UNPUBLISHED_DRAFT_MARKER = "追加編集された未公開の下書きがあります"
PLAN_NAME = "AI Decision Intelligence"
PLAN_ADDED_MARKER = f"{PLAN_NAME} 追加済"
ALL_PLANS_NOT_ADDED_MARKER = "すべてのプラン（全員に公開） 追加"


def _canon(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _visible_exact_button_count(page: Any, label: str) -> int:
    values = [_canon(v) for v in page.locator("button:visible").all_text_contents()]
    return sum(1 for value in values if value == label)


def _public_card_after_update(page: Any) -> dict[str, Any]:
    page.goto(run319.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1800)
    if base._looks_logged_out(page):
        raise base.NoteAuthenticationExpired("Run325 post-update article-list browser is not authenticated")
    card = run319._mark_target_card(page)
    if not card.get("cardFound"):
        raise base.NoteDraftError("Run325 could not find exact target card after update")
    text = _canon(card.get("cardText"))
    if run315.NEW_TITLE not in text:
        raise base.NoteDraftError(f"Run325 post-update card does not show new title: {text[:1000]}")
    if "公開中" not in text:
        raise base.NoteDraftError(f"Run325 post-update card is not public: {text[:1000]}")
    if UNPUBLISHED_DRAFT_MARKER in text:
        raise base.NoteDraftError(f"Run325 post-update card still reports an unpublished draft: {text[:1000]}")
    if run315.AUDITED_TITLE in text:
        raise base.NoteDraftError("Run325 post-update card still shows the legacy published title")
    return card


def _membership_state_after_update(page: Any, card: dict[str, Any]) -> dict[str, Any]:
    menu = run319._open_menu_if_exact(page, card)
    if not menu.get("opened"):
        raise base.NoteDraftError(f"Run325 could not open target menu for membership verification: {menu}")
    run320._visible_exact(page, role="menuitem", name=run320.MENU_ACTION_LABEL).click()
    page.wait_for_timeout(900)
    surface = run320._membership_surface(page)
    dialog_text = " ".join(
        _canon(row.get("text"))
        for row in (surface.get("dialogs") or [])
        if isinstance(row, dict)
    )
    if PLAN_ADDED_MARKER not in dialog_text:
        raise base.NoteDraftError(
            f"Run325 membership postcondition failed: missing {PLAN_ADDED_MARKER!r}: {dialog_text[:2000]}"
        )
    if ALL_PLANS_NOT_ADDED_MARKER not in dialog_text:
        raise base.NoteDraftError(
            "Run325 membership postcondition failed: all-plans exposure appears to have changed"
        )
    return {
        "menu": menu,
        "dialog_text": dialog_text,
        "plan_added": True,
        "all_plans_not_added": True,
    }


def finalize() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_FINALIZE_LATEST_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run325 exact finalize confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run325") from exc

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

                # Exact source proof in a clean cookie-only browser.
                _, body, source_title, source_body_text = run317._open_exact_clean_editor(page)
                source_sha = run315._sha256(source_body_text)
                if source_title != run315.NEW_TITLE or source_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run325 refuses non-authorized source state: title={source_title!r} sha256={source_sha}"
                    )
                run315._verify_editor(body)

                # Existing article -> edit -> latest unpublished draft, exactly as Run322/324 proved.
                page.goto(run319.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1600)
                pre_card = run319._mark_target_card(page)
                if not pre_card.get("cardFound"):
                    raise base.NoteDraftError("Run325 exact target article card was not found")
                pre_card_text = _canon(pre_card.get("cardText"))

                # Idempotency guard: if note no longer reports a newer draft and the public card already
                # shows the exact new title, do not click any public-update control again.
                if run315.NEW_TITLE in pre_card_text and UNPUBLISHED_DRAFT_MARKER not in pre_card_text and "公開中" in pre_card_text:
                    membership = _membership_state_after_update(page, pre_card)
                    return {
                        "status": "already_current_verified_no_mutation",
                        "target_note_id": run315.TARGET_NOTE_ID,
                        "source_title": source_title,
                        "source_body_sha256": source_sha,
                        "pre_card": pre_card,
                        "post_card": pre_card,
                        "membership_postcondition": membership,
                        "trial_read_line_clicked": False,
                        "final_update_clicked": False,
                        "public_mutation": False,
                        "membership_mutation": False,
                        "settings_mutation": False,
                        "zero_gemini_calls": True,
                        "notion_writes": 0,
                    }

                if UNPUBLISHED_DRAFT_MARKER not in pre_card_text:
                    raise base.NoteDraftError(
                        f"Run325 refuses ambiguous pre-update card without expected unpublished-draft marker: {pre_card_text[:1200]}"
                    )
                if run315.AUDITED_TITLE not in pre_card_text:
                    raise base.NoteDraftError(
                        f"Run325 refuses unexpected currently published title: {pre_card_text[:1200]}"
                    )

                menu = run319._open_menu_if_exact(page, pre_card)
                if not menu.get("opened"):
                    raise base.NoteDraftError(f"Run325 exact target menu did not open: {menu}")
                run321._visible_exact(page, role="menuitem", name=run321.EDIT_LABEL).click()
                page.wait_for_timeout(700)
                version_route = run322._select_latest_and_confirm(page)
                page.wait_for_timeout(700)

                title_field = base._find_title(page)
                routed_body = base._find_body(page, title_field)
                routed_title = run315._field_text(title_field)
                routed_body_text = run315._body_text(routed_body)
                routed_sha = run315._sha256(routed_body_text)
                if routed_title != run315.NEW_TITLE or routed_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run325 routed revision mismatch: title={routed_title!r} sha256={routed_sha}"
                    )
                run315._verify_editor(routed_body)

                run310._unique_button(page, "公開に進む").click()
                try:
                    page.wait_for_url(f"**/notes/{run315.TARGET_NOTE_ID}/publish/**", timeout=15000)
                except Exception as exc:
                    raise base.NoteDraftError("Run325 did not reach exact publish settings") from exc
                if not str(page.url or "").startswith(run315.TARGET_PUBLISH_URL):
                    raise base.NoteDraftError(f"Run325 publish URL drifted: {page.url}")
                page.wait_for_timeout(1200)

                # Run324 precondition: no final update yet, exactly one trial-read intermediate CTA.
                if _visible_exact_button_count(page, FINAL_UPDATE_LABEL) != 0:
                    raise base.NoteDraftError("Run325 expected no direct update CTA before trial-read setup")
                if _visible_exact_button_count(page, TRIAL_READ_LABEL) != 1:
                    raise base.NoteDraftError("Run325 expected exactly one trial-read setup CTA")

                run310._unique_button(page, TRIAL_READ_LABEL).click()
                page.wait_for_timeout(1000)

                # Preserve members-only access: inventory line candidates but click none of them.
                line_candidate_count = run324._line_candidate_count(page)
                if line_candidate_count < 1:
                    raise base.NoteDraftError("Run325 trial-read surface exposed no line candidates")
                if _visible_exact_button_count(page, FINAL_UPDATE_LABEL) != 1:
                    raise base.NoteDraftError("Run325 trial-read surface did not expose exactly one final update CTA")

                pre_commit_url = str(page.url or "")
                run310._unique_button(page, FINAL_UPDATE_LABEL).click()
                page.wait_for_timeout(2600)

                # Strong postconditions: public card converged and there is no newer unpublished draft.
                post_card = _public_card_after_update(page)
                membership = _membership_state_after_update(page, post_card)

                screenshot_file = os.environ.get(SCREENSHOT_ENV, "").strip()
                if screenshot_file:
                    path = Path(screenshot_file)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(path), full_page=True)

                return {
                    "status": "latest_draft_published_and_membership_verified",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": source_title,
                    "source_body_sha256": source_sha,
                    "routed_title": routed_title,
                    "routed_body_sha256": routed_sha,
                    "version_route": version_route,
                    "pre_card": pre_card,
                    "post_card": post_card,
                    "pre_commit_url": pre_commit_url,
                    "trial_read_line_candidate_count": line_candidate_count,
                    "trial_read_line_clicked": False,
                    "final_update_clicked": True,
                    "membership_postcondition": membership,
                    "members_only_access_preserved": True,
                    "all_plans_exposure_preserved_false": True,
                    "public_mutation": True,
                    "membership_mutation": False,
                    "settings_mutation": False,
                    "zero_gemini_calls": True,
                    "notion_writes": 0,
                    "screenshot_written": bool(screenshot_file),
                }
            finally:
                context.close()
        finally:
            browser.close()


def main() -> None:
    result = finalize()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN325_MEMBER_ONBOARDING_FINALIZE_LATEST=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
