#!/usr/bin/env python3
"""Run320: probe the exact existing-article membership dialog without committing.

Run317 proved the rewritten onboarding article is saved on note's server. Run319 then proved
that the exact article-list card exposes `メンバーシップ特典追加・解除`. Run320 clicks only
that exact menu action to inspect the resulting membership-selection surface. It never selects
a membership, never clicks an add/save/confirm action, and never publishes the article.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run315_member_onboarding_update as run315
import run316_member_onboarding_finalize_probe as run316
import run317_member_onboarding_server_save as run317
import run318_member_onboarding_publish_cta_probe as run318
import run319_member_onboarding_article_list_probe as run319

CONFIRM_TOKEN = "PROBE_MEMBER_ONBOARDING_MEMBERSHIP_DIALOG_N284E428C80F4_SHAAAB9E57B"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_MEMBERSHIP_DIALOG_PROBE_RESULT_FILE"
MENU_ACTION_LABEL = "メンバーシップ特典追加・解除"


def _visible_exact(page: Any, *, role: str, name: str) -> Any:
    locator = page.get_by_role(role, name=name, exact=True)
    visible: list[Any] = []
    for idx in range(locator.count()):
        item = locator.nth(idx)
        try:
            if item.is_visible():
                visible.append(item)
        except Exception:
            pass
    if len(visible) != 1:
        raise base.NoteDraftError(
            f"Run320 expected one exact visible {role} {name!r}; got {len(visible)}"
        )
    return visible[0]


def _membership_surface(page: Any) -> dict[str, Any]:
    script = r"""
    () => {
      const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
      };
      const labels = (el) => {
        const out = [];
        if (el.id) {
          const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
          if (lab) out.push(norm(lab.innerText));
        }
        const parent = el.closest('label');
        if (parent) out.push(norm(parent.innerText));
        let cur = el.parentElement;
        for (let i = 0; i < 4 && cur; i++, cur = cur.parentElement) {
          const t = norm(cur.innerText);
          if (t) out.push(t.slice(0, 700));
        }
        return Array.from(new Set(out.filter(Boolean))).slice(0, 5);
      };
      const controls = Array.from(document.querySelectorAll(
        'button,[role="button"],[role="menuitem"],[role="radio"],[role="checkbox"],input,select,a[href]'
      ))
        .filter(visible)
        .slice(0, 260)
        .map((el, index) => ({
          index,
          tag: el.tagName.toLowerCase(),
          role: el.getAttribute('role') || '',
          type: el.getAttribute('type') || '',
          text: norm(el.innerText || el.value || ''),
          ariaLabel: el.getAttribute('aria-label') || '',
          ariaChecked: el.getAttribute('aria-checked') || '',
          checked: typeof el.checked === 'boolean' ? el.checked : null,
          disabled: !!el.disabled,
          ariaDisabled: el.getAttribute('aria-disabled') || '',
          href: el.getAttribute('href') || '',
          context: labels(el),
        }));
      const dialogs = Array.from(document.querySelectorAll('[role="dialog"]'))
        .filter(visible)
        .map((el, index) => ({index, text:norm(el.innerText).slice(0,12000)}));
      return {controls, dialogs, bodyText:norm(document.body.innerText).slice(0,20000)};
    }
    """
    value = page.evaluate(script)
    return value if isinstance(value, dict) else {"controls": [], "dialogs": [], "bodyText": ""}


def _candidate_confirm_controls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers = (
        "追加",
        "追加する",
        "保存",
        "保存する",
        "決定",
        "完了",
        "更新",
        "更新する",
        "設定",
        "設定する",
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        text = str(row.get("text") or "").strip()
        aria = str(row.get("ariaLabel") or "").strip()
        if text in markers or aria in markers:
            out.append(row)
    return out


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_MEMBERSHIP_DIALOG_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run320 exact membership-dialog probe confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run320") from exc

    with sync_playwright() as playwright:
        cookies = run318._cookie_source(playwright)
        browser = run317._launch_clean_browser(playwright)
        try:
            context = run317._new_cookie_only_context(browser, cookies)
            try:
                page = context.new_page()
                page.set_default_timeout(30000)

                # Re-prove the exact server-saved draft in a clean cookie-only context.
                _, body, title, body_text = run317._open_exact_clean_editor(page)
                body_sha = run315._sha256(body_text)
                if title != run315.NEW_TITLE or body_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run320 refuses non-server-saved source state: title={title!r} sha256={body_sha}"
                    )
                run315._verify_editor(body)

                page.goto(run319.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1800)
                if base._looks_logged_out(page):
                    raise base.NoteAuthenticationExpired("Run320 clean article-list browser is not authenticated")

                card_info = run319._mark_target_card(page)
                if not card_info.get("cardFound"):
                    raise base.NoteDraftError("Run320 exact target article card was not found")
                menu = run319._open_menu_if_exact(page, card_info)
                if not menu.get("opened"):
                    raise base.NoteDraftError(f"Run320 exact target menu did not open: {menu}")

                menu_action = _visible_exact(page, role="menuitem", name=MENU_ACTION_LABEL)
                menu_action.click()
                page.wait_for_timeout(1000)

                surface = _membership_surface(page)
                controls = surface.get("controls") if isinstance(surface.get("controls"), list) else []
                dialogs = surface.get("dialogs") if isinstance(surface.get("dialogs"), list) else []
                body_text_after = str(surface.get("bodyText") or "")
                membership_mentions = [
                    row for row in controls
                    if run315.MEMBERSHIP_NAME in " ".join(
                        [
                            str(row.get("text") or ""),
                            str(row.get("ariaLabel") or ""),
                            " ".join(str(x) for x in (row.get("context") or [])),
                        ]
                    )
                ]
                confirm_candidates = _candidate_confirm_controls(controls)

                return {
                    "status": "probe_complete_no_membership_mutation",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": title,
                    "source_body_sha256": body_sha,
                    "fresh_cookie_only_context": True,
                    "local_storage_seeded": False,
                    "target_card": card_info,
                    "target_menu": menu,
                    "membership_menu_action": MENU_ACTION_LABEL,
                    "membership_menu_action_opened": True,
                    "surface_dialogs": dialogs,
                    "surface_controls": controls,
                    "membership_mentions": membership_mentions,
                    "confirm_candidates": confirm_candidates,
                    "surface_text_excerpt": body_text_after,
                    "membership_selection_clicked": False,
                    "final_confirm_clicked": False,
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
    print("RUN320_MEMBER_ONBOARDING_MEMBERSHIP_DIALOG_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
