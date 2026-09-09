#!/usr/bin/env python3
"""Run319: probe the existing-article membership-add route from note's article list.

Run317 proved the rewritten onboarding body is server-persisted. Run318 proved this special
sales-stopped article exposes no final update/publish CTA in publish settings. note's current
official help says an already-published article should be associated to membership from
`自分の記事` -> exact article `...` menu -> `メンバーシップ特典に追加`.

Run319 observes that exact route in a clean cookie-only browser. It may open the target article's
menu, but never chooses a menu action and never mutates article/membership/public state.
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

CONFIRM_TOKEN = "PROBE_MEMBER_ONBOARDING_ARTICLE_LIST_N284E428C80F4_SHAAAB9E57B"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_ARTICLE_LIST_PROBE_RESULT_FILE"
ARTICLE_LIST_URL = "https://note.com/notes"
TARGET_PUBLIC_PATH = f"/trendhub_biz/n/{run315.TARGET_NOTE_ID}"


def _mark_target_card(page: Any) -> dict[str, Any]:
    script = r"""
    (needle) => {
      const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
      };
      const anchors = Array.from(document.querySelectorAll('a[href]'))
        .filter(a => String(a.getAttribute('href') || '').includes(needle) && visible(a));
      if (!anchors.length) return {found:false, anchorCount:0};
      const anchor = anchors[0];
      let chosen = null;
      let cur = anchor.parentElement;
      for (let depth = 0; depth < 12 && cur; depth++, cur = cur.parentElement) {
        const buttons = Array.from(cur.querySelectorAll('button,[role="button"]')).filter(visible);
        const targetLinks = Array.from(cur.querySelectorAll('a[href]'))
          .filter(a => String(a.getAttribute('href') || '').includes(needle));
        const text = norm(cur.innerText);
        if (buttons.length >= 1 && targetLinks.length >= 1 && text.length > 0 && text.length < 5000) {
          chosen = cur;
          break;
        }
      }
      if (!chosen) return {found:true, anchorCount:anchors.length, cardFound:false};
      chosen.setAttribute('data-run319-target-card', '1');
      const controls = Array.from(chosen.querySelectorAll('button,[role="button"],a[href]')).map((el, index) => ({
        index,
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') || '',
        text: norm(el.innerText || el.value || ''),
        ariaLabel: el.getAttribute('aria-label') || '',
        title: el.getAttribute('title') || '',
        href: el.getAttribute('href') || '',
        visible: visible(el),
        hasSvg: !!el.querySelector('svg'),
      }));
      return {
        found:true,
        anchorCount:anchors.length,
        cardFound:true,
        cardText:norm(chosen.innerText).slice(0,4000),
        cardControls:controls.slice(0,80),
      };
    }
    """
    value = page.evaluate(script, TARGET_PUBLIC_PATH)
    return value if isinstance(value, dict) else {"found": False}


def _menu_candidate_indices(card_info: dict[str, Any]) -> list[int]:
    controls = card_info.get("cardControls") or []
    buttons = [row for row in controls if row.get("tag") == "button" or row.get("role") == "button"]
    semantic: list[int] = []
    glyphs = {"...", "…", "⋯", "︙", "•••"}
    for row in buttons:
        text = str(row.get("text") or "").strip()
        aria = str(row.get("ariaLabel") or "").strip()
        title = str(row.get("title") or "").strip()
        combined = " ".join((text, aria, title))
        if text in glyphs or "メニュー" in combined or "その他" in combined:
            semantic.append(int(row.get("index")))
    if semantic:
        return semantic
    empty_svg = [
        int(row.get("index"))
        for row in buttons
        if not str(row.get("text") or "").strip()
        and bool(row.get("hasSvg"))
        and bool(row.get("visible"))
    ]
    return empty_svg if len(empty_svg) == 1 else []


def _open_menu_if_exact(page: Any, card_info: dict[str, Any]) -> dict[str, Any]:
    indices = _menu_candidate_indices(card_info)
    if len(indices) != 1:
        return {"opened": False, "candidate_indices": indices, "reason": "menu_not_uniquely_identified"}
    target_index = indices[0]
    card = page.locator('[data-run319-target-card="1"]')
    controls = card.locator('button,[role="button"],a[href]')
    if target_index >= controls.count():
        raise base.NoteDraftError("Run319 menu candidate index drifted before click")
    candidate = controls.nth(target_index)
    if not candidate.is_visible():
        raise base.NoteDraftError("Run319 exact menu candidate is not visible")
    candidate.click()
    page.wait_for_timeout(700)
    return {"opened": True, "candidate_indices": indices}


def _membership_menu_matches(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers = ("メンバーシップ特典に追加", "メンバーシップに追加", "メンバー特典記事")
    return [
        row for row in rows
        if any(marker in " ".join((str(row.get("text") or ""), str(row.get("ariaLabel") or ""), str(row.get("title") or ""))) for marker in markers)
    ]


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_ARTICLE_LIST_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run319 exact article-list probe confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run319") from exc

    with sync_playwright() as playwright:
        cookies = run318._cookie_source(playwright)
        browser = run317._launch_clean_browser(playwright)
        try:
            context = run317._new_cookie_only_context(browser, cookies)
            try:
                page = context.new_page()
                page.set_default_timeout(30000)

                # Prove this clean session still sees the exact server-saved authorized revision.
                _, body, title, body_text = run317._open_exact_clean_editor(page)
                body_sha = run315._sha256(body_text)
                if title != run315.NEW_TITLE or body_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run319 refuses non-server-saved source state: title={title!r} sha256={body_sha}"
                    )
                run315._verify_editor(body)

                page.goto(ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1800)
                if base._looks_logged_out(page):
                    raise base.NoteAuthenticationExpired("Run319 clean article-list browser is not authenticated")

                card_info = _mark_target_card(page)
                menu = {"opened": False, "reason": "target_card_not_found"}
                before = run316._control_inventory(page)
                after = before
                membership_matches: list[dict[str, Any]] = []
                if card_info.get("cardFound"):
                    menu = _open_menu_if_exact(page, card_info)
                    if menu.get("opened"):
                        after = run316._control_inventory(page)
                        membership_matches = _membership_menu_matches(after)

                page_text = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
                return {
                    "status": "probe_complete_no_mutation",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": title,
                    "source_body_sha256": body_sha,
                    "fresh_cookie_only_context": True,
                    "local_storage_seeded": False,
                    "article_list_url": str(page.url or ""),
                    "target_card": card_info,
                    "menu": menu,
                    "controls_before_menu": before,
                    "controls_after_menu": after,
                    "membership_menu_matches": membership_matches,
                    "page_text_excerpt": page_text[:18000],
                    "menu_action_clicked": False,
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
    print("RUN319_MEMBER_ONBOARDING_ARTICLE_LIST_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
