#!/usr/bin/env python3
"""Run333: replace only the stale AI Decision Intelligence membership description.

The Run332 live probe proved the exact owner edit route, current description field, 140-character
UI limit, and final `プランを変更する` control. Run333 is a hard-bound maintenance exception:
- exact membership plan id/route only;
- public and edit-form description must be exactly the audited legacy copy or already-current copy;
- mutate only that one description textarea;
- preserve every other plan-form input/textarea/select state and existing benefit labels;
- click exactly one visible enabled `プランを変更する` button when a change is required;
- fresh edit-form + public-profile verification after the save;
- idempotent no-op if already current;
- zero Gemini/model calls and zero Notion writes.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run330_note_profile_exact_update as profile
import run332_membership_description_edit_route_probe as run332

CONFIRM_TOKEN = "UPDATE_MEMBERSHIP_DESCRIPTION_AI_DECISION_INTELLIGENCE_RUN333_EXACT"
RESULT_ENV = "NOTE_MEMBERSHIP_DESCRIPTION_RUN333_RESULT_FILE"
EDIT_URL = "https://note.com/membership/settings/plans/358b94bcb3c6/edit"
PUBLIC_PROFILE_URL = run332.PUBLIC_PROFILE_URL
MEMBERSHIP_NAME = run332.MEMBERSHIP_NAME
OLD_DESCRIPTION = (
    'AIニュースを追う時間を減らし、「このAIを使うべきか」をすばやく判断。'
    '実用性・リスク・向いている用途・一次情報をまとめた会員向けDB＋ダイジェストです。\n\n'
    '参加後は、メンバー限定記事「はじめに｜AI Decision Intelligenceの利用方法」をご確認ください。'
)
NEW_DESCRIPTION = (
    'AIニュースを追う時間を減らし、「このAIを使うべきか」をすばやく判断。'
    '実用性・リスク・向いている用途・一次情報をまとめた会員向けDB＋ダイジェストです。\n\n'
    '参加後は、メンバー限定の「最初にお読みください」記事をご確認ください。'
)
MAX_UI_CHARS = 140
FINAL_BUTTON = "プランを変更する"
EXPECTED_PLAN_NAME = MEMBERSHIP_NAME
EXPECTED_FEE_MARKER = "1,980 円/月"
EXPECTED_BENEFITS = (
    "特典を削除: AI Decision Intelligence｜会員向け意思決定DB",
    "特典を削除: AI Decision Intelligence｜会員向けDigest",
)


def _canon(value: Any) -> str:
    return " ".join(str(value or "").split())


def _description_state(value: str) -> str:
    text = _canon(value)
    if text == _canon(OLD_DESCRIPTION):
        return "legacy"
    if text == _canon(NEW_DESCRIPTION):
        return "current"
    return "unexpected"


def _public_description_state(page: Any) -> str:
    if profile._public_state(page) != "current":
        raise base.NoteDraftError("Run333 refuses a non-current public profile state")
    body = _canon(page.locator("body").inner_text(timeout=10000))
    old = _canon(OLD_DESCRIPTION)
    new = _canon(NEW_DESCRIPTION)
    if MEMBERSHIP_NAME not in body:
        raise base.NoteDraftError("Run333 target membership card is missing")
    if new in body and run332.LEGACY_REFERENCE not in body:
        return "current"
    if old in body and run332.LEGACY_REFERENCE in body and new not in body:
        return "legacy"
    raise base.NoteDraftError("Run333 refuses an unexpected public membership-description state")


def _open_exact_edit(page: Any, expected_state: str) -> tuple[Any, list[dict[str, Any]]]:
    page.goto(EDIT_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1600)
    if base._looks_logged_out(page):
        raise base.NoteAuthenticationExpired("Run333 membership edit route is not authenticated")
    if str(page.url or "").split("?", 1)[0].rstrip("/") != EDIT_URL.rstrip("/"):
        raise base.NoteDraftError(f"Run333 unexpected membership edit route: {page.url!r}")

    body = _canon(page.locator("body").inner_text(timeout=10000))
    if "プラン編集" not in body or EXPECTED_FEE_MARKER not in body:
        raise base.NoteDraftError("Run333 target plan edit markers are missing")

    plan_names = page.locator('input[type="text"]:visible')
    exact_plan_inputs: list[Any] = []
    for idx in range(plan_names.count()):
        item = plan_names.nth(idx)
        try:
            if _canon(item.input_value()) == EXPECTED_PLAN_NAME:
                exact_plan_inputs.append(item)
        except Exception:
            pass
    if len(exact_plan_inputs) != 1:
        raise base.NoteDraftError(f"Run333 expected one exact plan-name input; observed {len(exact_plan_inputs)}")

    candidates = page.locator("textarea:visible")
    matches: list[Any] = []
    for idx in range(candidates.count()):
        item = candidates.nth(idx)
        try:
            state = _description_state(item.input_value())
            if state in {"legacy", "current"}:
                matches.append(item)
        except Exception:
            pass
    if len(matches) != 1:
        raise base.NoteDraftError(f"Run333 expected one exact description textarea; observed {len(matches)}")
    description = matches[0]
    actual_state = _description_state(description.input_value())
    if actual_state != expected_state:
        raise base.NoteDraftError(
            f"Run333 public/edit description state mismatch: public={expected_state!r} edit={actual_state!r}"
        )

    snapshot = _other_plan_snapshot(page, description)
    if tuple(snapshot.get("benefitLabels") or ()) != EXPECTED_BENEFITS:
        raise base.NoteDraftError(
            f"Run333 existing benefits differ from audited state: {snapshot.get('benefitLabels')!r}"
        )
    return description, snapshot


def _other_plan_snapshot(page: Any, description: Any) -> dict[str, Any]:
    value = page.evaluate(
        r"""
        (descriptionEl) => {
          const form = descriptionEl.closest('form');
          if (!form) return null;
          const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
          const controls = [];
          const counts = {};
          for (const el of Array.from(form.querySelectorAll('input,textarea,select'))) {
            if (el === descriptionEl) continue;
            if (el.getAttribute('type') === 'file') continue;
            const row = {
              tag: el.tagName.toLowerCase(),
              type: el.getAttribute('type') || '',
              role: el.getAttribute('role') || '',
              name: el.getAttribute('name') || '',
              ariaLabel: el.getAttribute('aria-label') || '',
              value: 'value' in el ? String(el.value || '') : '',
              checked: 'checked' in el ? Boolean(el.checked) : null,
            };
            const base = [row.tag,row.type,row.role,row.name,row.ariaLabel].join('|');
            row.occurrence = counts[base] || 0;
            counts[base] = row.occurrence + 1;
            controls.push(row);
          }
          controls.sort((a,b) => JSON.stringify([
            a.tag,a.type,a.role,a.name,a.ariaLabel,a.occurrence
          ]).localeCompare(JSON.stringify([
            b.tag,b.type,b.role,b.name,b.ariaLabel,b.occurrence
          ])));
          const benefitLabels = Array.from(form.querySelectorAll('button[aria-label]'))
            .map(el => el.getAttribute('aria-label') || '')
            .filter(s => s.startsWith('特典を削除:'))
            .sort();
          return {controls, benefitLabels, formText: norm(form.innerText).slice(0,9000)};
        }
        """,
        description,
    )
    if not isinstance(value, dict):
        raise base.NoteDraftError("Run333 could not snapshot the target plan form")
    return value


def _snapshot_diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    if before == after:
        return ""
    return json.dumps({"before": before, "after": after}, ensure_ascii=False)[:2400]


def _require_other_settings_unchanged(before: dict[str, Any], after: dict[str, Any], stage: str) -> None:
    diff = _snapshot_diff(before, after)
    if diff:
        raise base.NoteDraftError(f"Run333 detected unrelated plan-setting change {stage}; diff={diff}")


def _final_button(page: Any) -> Any:
    pattern = re.compile(r"^\s*プランを変更する\s*$")
    locator = page.locator("button:visible").filter(has_text=pattern)
    matches: list[Any] = []
    for idx in range(locator.count()):
        item = locator.nth(idx)
        try:
            if _canon(item.inner_text()) == FINAL_BUTTON:
                matches.append(item)
        except Exception:
            pass
    if len(matches) != 1:
        raise base.NoteDraftError(f"Run333 expected one exact final button; observed {len(matches)}")
    button = matches[0]
    if not button.is_enabled():
        raise base.NoteDraftError("Run333 exact final button is disabled")
    return button


def _verify_public_current_with_retry(page: Any) -> None:
    last = ""
    for _ in range(6):
        try:
            state = _public_description_state(page)
            if state == "current":
                return
            last = state
        except Exception as exc:
            last = repr(exc)
        page.wait_for_timeout(900)
    raise base.NoteDraftError(f"Run333 public verification did not reach current description: {last}")


def update() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBERSHIP_DESCRIPTION_RUN333_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run333 exact maintenance confirmation token is missing or invalid")
    if len(NEW_DESCRIPTION) > MAX_UI_CHARS:
        raise base.NoteDraftError(
            f"Run333 new description exceeds audited {MAX_UI_CHARS}-character UI limit: {len(NEW_DESCRIPTION)}"
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run333") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        save_clicks = 0
        try:
            public_state = _public_description_state(page)
            description, before = _open_exact_edit(page, public_state)

            if public_state == "current":
                return {
                    "status": "already_current_verified_no_mutation",
                    "membership_name": MEMBERSHIP_NAME,
                    "edit_url": EDIT_URL,
                    "description_chars": len(NEW_DESCRIPTION),
                    "description_mutation": False,
                    "other_plan_settings_unchanged": True,
                    "save_clicks": 0,
                    "membership_mutation": False,
                    "public_mutation": False,
                    "legacy_reference_present": False,
                    "zero_gemini_calls": True,
                    "notion_writes": 0,
                }

            description.fill(NEW_DESCRIPTION)
            page.wait_for_timeout(350)
            if _canon(description.input_value()) != _canon(NEW_DESCRIPTION):
                raise base.NoteDraftError("Run333 description field does not contain the exact authorized copy")
            _require_other_settings_unchanged(before, _other_plan_snapshot(page, description), "before save")

            button = _final_button(page)
            button.click()
            save_clicks += 1
            page.wait_for_timeout(2200)
            if save_clicks != 1:
                raise base.NoteDraftError("Run333 exact-one-save-click contract failed")

            _verify_public_current_with_retry(page)
            fresh_description, after = _open_exact_edit(page, "current")
            if _canon(fresh_description.input_value()) != _canon(NEW_DESCRIPTION):
                raise base.NoteDraftError("Run333 fresh edit verification did not preserve current description")
            _require_other_settings_unchanged(before, after, "on fresh verification")
            _verify_public_current_with_retry(page)

            return {
                "status": "updated_and_verified_exact_description_only",
                "membership_name": MEMBERSHIP_NAME,
                "edit_url": EDIT_URL,
                "description_chars": len(NEW_DESCRIPTION),
                "description_mutation": True,
                "other_plan_settings_unchanged": True,
                "save_clicks": save_clicks,
                "membership_mutation": True,
                "public_mutation": True,
                "legacy_reference_present": False,
                "zero_gemini_calls": True,
                "notion_writes": 0,
            }
        finally:
            context.close()


def main() -> None:
    result = update()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN333_MEMBERSHIP_DESCRIPTION_EXACT_UPDATE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
