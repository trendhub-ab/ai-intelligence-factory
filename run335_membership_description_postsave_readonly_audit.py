#!/usr/bin/env python3
"""Run335: read-only audit after Run334 post-save public verification failed.

The Run334 live execution reached the exact final button and then observed the public membership
card still in the legacy-copy state. Run335 resolves the ambiguity without another mutation:
- inspect the public membership card and classify its description as legacy/current/unexpected;
- navigate directly to the exact audited owner edit URL (zero clicks);
- classify the actual saved edit-form description independently;
- verify exact plan name, fee marker, and the two audited benefits;
- perform zero fills, zero clicks, zero saves, zero model calls, and zero Notion writes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run330_note_profile_exact_update as profile
import run333_membership_description_exact_update as run333
import run334_membership_description_exact_update as run334

CONFIRM_TOKEN = "AUDIT_MEMBERSHIP_DESCRIPTION_POSTSAVE_RUN335_READONLY"
RESULT_ENV = "NOTE_MEMBERSHIP_DESCRIPTION_RUN335_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_MEMBERSHIP_DESCRIPTION_RUN335_SCREENSHOT_FILE"


def _canon(value: Any) -> str:
    return " ".join(str(value or "").split())


def _public_state(page: Any) -> str:
    page.goto(run333.PUBLIC_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1400)
    if profile._public_state(page) != "current":
        raise base.NoteDraftError("Run335 refuses a non-current public profile biography state")
    body = _canon(page.locator("body").inner_text(timeout=10000))
    if run333.MEMBERSHIP_NAME not in body:
        raise base.NoteDraftError("Run335 target membership card is missing")
    old = _canon(run333.OLD_DESCRIPTION)
    new = _canon(run333.NEW_DESCRIPTION)
    has_old = old in body
    has_new = new in body
    if has_old and not has_new:
        return "legacy"
    if has_new and not has_old:
        return "current"
    return "unexpected"


def _exact_plan_name(page: Any) -> str:
    rows = page.locator('input[type="text"]:visible')
    values: list[str] = []
    for idx in range(rows.count()):
        item = rows.nth(idx)
        try:
            value = _canon(item.input_value())
        except Exception:
            continue
        if value == run333.EXPECTED_PLAN_NAME:
            values.append(value)
    if len(values) != 1:
        raise base.NoteDraftError(f"Run335 expected one exact plan-name field; observed {len(values)}")
    return values[0]


def _description_locator(page: Any) -> tuple[Any, str]:
    rows = page.locator("textarea:visible")
    matched: list[tuple[Any, str]] = []
    for idx in range(rows.count()):
        item = rows.nth(idx)
        try:
            state = run333._description_state(item.input_value())
        except Exception:
            continue
        if state in {"legacy", "current"}:
            matched.append((item, state))
    if len(matched) != 1:
        raise base.NoteDraftError(f"Run335 expected one exact audited description textarea; observed {len(matched)}")
    return matched[0]


def audit() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBERSHIP_DESCRIPTION_RUN335_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run335 exact read-only confirmation token is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run335") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            public_state = _public_state(page)

            page.goto(run333.EDIT_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1600)
            if base._looks_logged_out(page):
                raise base.NoteAuthenticationExpired("Run335 membership edit route is not authenticated")
            if str(page.url or "").split("?", 1)[0].rstrip("/") != run333.EDIT_URL.rstrip("/"):
                raise base.NoteDraftError(f"Run335 unexpected edit route: {page.url!r}")

            body = _canon(page.locator("body").inner_text(timeout=10000))
            if "プラン編集" not in body or run333.EXPECTED_FEE_MARKER not in body:
                raise base.NoteDraftError("Run335 exact plan markers are missing")

            plan_name = _exact_plan_name(page)
            description, edit_state = _description_locator(page)
            snapshot = run334._other_plan_snapshot(page, description)
            benefit_labels = tuple(snapshot.get("benefitLabels") or ())
            if benefit_labels != run333.EXPECTED_BENEFITS:
                raise base.NoteDraftError(
                    f"Run335 existing benefits differ from audited state: {benefit_labels!r}"
                )

            screenshot_written = False
            screenshot_path = os.environ.get(SCREENSHOT_ENV, "").strip()
            if screenshot_path:
                target = Path(screenshot_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(target), full_page=True)
                screenshot_written = True

            return {
                "status": "postsave_state_audited_no_mutation",
                "public_state": public_state,
                "edit_state": edit_state,
                "public_edit_consistent": public_state == edit_state,
                "membership_name": run333.MEMBERSHIP_NAME,
                "plan_name_verified": plan_name == run333.EXPECTED_PLAN_NAME,
                "fee_marker_verified": run333.EXPECTED_FEE_MARKER in body,
                "benefits_verified": benefit_labels == run333.EXPECTED_BENEFITS,
                "description_chars": len(description.input_value()),
                "edit_url": str(page.url or ""),
                "clicks_performed": 0,
                "field_filled": False,
                "save_clicked": False,
                "membership_mutation": False,
                "public_mutation": False,
                "zero_gemini_calls": True,
                "notion_writes": 0,
                "screenshot_written": screenshot_written,
            }
        finally:
            context.close()


def main() -> None:
    result = audit()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN335_MEMBERSHIP_DESCRIPTION_POSTSAVE_AUDIT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
