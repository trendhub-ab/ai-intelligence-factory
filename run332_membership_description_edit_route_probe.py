#!/usr/bin/env python3
"""Run332: probe the current note membership-description edit route without mutation.

Purpose:
- the public AI Decision Intelligence membership card still references the legacy onboarding
  article title;
- identify the exact owner-only `編集する` href from the public membership card;
- navigate directly to that audited note.com href (never click it);
- inventory the current description field, length limit, and save/update controls;
- perform zero clicks, zero fills, zero saves, zero model calls, and zero Notion writes.

This probe does not authorize any membership or public-copy mutation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run315_member_onboarding_update as onboarding
import run330_note_profile_exact_update as profile

CONFIRM_TOKEN = "PROBE_MEMBERSHIP_DESCRIPTION_EDIT_ROUTE_AI_DECISION_INTELLIGENCE_READONLY"
RESULT_ENV = "NOTE_MEMBERSHIP_DESCRIPTION_ROUTE_PROBE_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_MEMBERSHIP_DESCRIPTION_ROUTE_PROBE_SCREENSHOT_FILE"
PUBLIC_PROFILE_URL = "https://note.com/trendhub_biz"
MEMBERSHIP_NAME = "AI Decision Intelligence"
LEGACY_REFERENCE = "はじめに｜AI Decision Intelligenceの利用方法"
CURRENT_ONBOARDING_TITLE = onboarding.NEW_TITLE
EDIT_LABEL = "編集する"


def _canon(value: Any) -> str:
    return " ".join(str(value or "").split())


def _find_membership_edit_link(page: Any) -> dict[str, Any]:
    value = page.evaluate(
        r"""
        ({membershipName, editLabel}) => {
          const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
          const visible = (el) => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' &&
              s.visibility !== 'hidden';
          };
          const out = [];
          for (const a of Array.from(document.querySelectorAll('a[href]'))) {
            if (!visible(a) || norm(a.innerText) !== editLabel) continue;
            let cur = a;
            let matched = null;
            for (let depth = 0; depth < 9 && cur; depth++, cur = cur.parentElement) {
              const text = norm(cur.innerText);
              if (text.includes(membershipName) && (text.includes('1,980') || text.includes('¥1,980'))) {
                matched = {depth, context: text.slice(0, 3500)};
                break;
              }
            }
            if (!matched) continue;
            out.push({
              href: new URL(a.getAttribute('href'), location.href).href,
              text: norm(a.innerText),
              ariaLabel: a.getAttribute('aria-label') || '',
              context: matched.context,
              depth: matched.depth,
            });
          }
          return out;
        }
        """,
        {"membershipName": MEMBERSHIP_NAME, "editLabel": EDIT_LABEL},
    )
    rows = value if isinstance(value, list) else []
    if len(rows) != 1:
        raise base.NoteDraftError(
            f"Run332 expected exactly one membership-scoped 編集する link; observed {len(rows)}"
        )
    row = rows[0]
    href = str(row.get("href") or "").strip()
    parsed = urlparse(href)
    if parsed.scheme != "https" or parsed.netloc != "note.com" or not parsed.path:
        raise base.NoteDraftError(f"Run332 refuses unexpected membership edit href: {href!r}")
    return row


def _surface_inventory(page: Any) -> dict[str, Any]:
    value = page.evaluate(
        r"""
        ({legacyReference, membershipName}) => {
          const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
          const visible = (el) => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' &&
              s.visibility !== 'hidden';
          };
          const entries = Array.from(document.querySelectorAll('input,textarea,select'))
            .filter(el => visible(el))
            .map((el, index) => {
              const rawValue = 'value' in el ? String(el.value || '') : '';
              const text = norm(rawValue);
              return {
                index,
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || '',
                name: el.getAttribute('name') || '',
                id: el.id || '',
                placeholder: el.getAttribute('placeholder') || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                maxLength: typeof el.maxLength === 'number' ? el.maxLength : null,
                textLength: rawValue.length,
                valueExcerpt: (text.includes(legacyReference) || text.includes(membershipName))
                  ? text.slice(0, 2500) : '',
                disabled: Boolean(el.disabled),
              };
            });
          const actions = Array.from(document.querySelectorAll('button,[role="button"],a[href]'))
            .filter(visible)
            .map((el, index) => ({
              index,
              tag: el.tagName.toLowerCase(),
              role: el.getAttribute('role') || '',
              text: norm(el.innerText).slice(0, 500),
              ariaLabel: el.getAttribute('aria-label') || '',
              disabled: Boolean(el.disabled),
              ariaDisabled: el.getAttribute('aria-disabled') || '',
              href: el.tagName.toLowerCase() === 'a'
                ? new URL(el.getAttribute('href'), location.href).href : '',
            }));
          const bodyText = norm(document.body.innerText).slice(0, 24000);
          return {entries, actions, bodyText};
        }
        """,
        {"legacyReference": LEGACY_REFERENCE, "membershipName": MEMBERSHIP_NAME},
    )
    return value if isinstance(value, dict) else {"entries": [], "actions": [], "bodyText": ""}


def _description_candidates(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in entries:
        excerpt = _canon(row.get("valueExcerpt"))
        placeholder = _canon(row.get("placeholder"))
        aria = _canon(row.get("ariaLabel"))
        if LEGACY_REFERENCE in excerpt or (
            MEMBERSHIP_NAME in excerpt and row.get("tag") == "textarea"
        ) or any(marker in (placeholder + " " + aria) for marker in ("説明", "紹介")):
            out.append(row)
    return out


def _save_candidates(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers = {"保存", "保存する", "更新", "更新する", "変更を保存", "設定する"}
    out: list[dict[str, Any]] = []
    for row in actions:
        text = _canon(row.get("text"))
        aria = _canon(row.get("ariaLabel"))
        if text in markers or aria in markers:
            out.append(row)
    return out


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBERSHIP_DESCRIPTION_ROUTE_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run332 exact read-only confirmation token is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run332") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            if profile._public_state(page) != "current":
                raise base.NoteDraftError("Run332 refuses a non-current public profile state")
            public_body = _canon(page.locator("body").inner_text(timeout=10000))
            if MEMBERSHIP_NAME not in public_body:
                raise base.NoteDraftError("Run332 membership card is missing from public profile")
            if LEGACY_REFERENCE not in public_body:
                raise base.NoteDraftError(
                    "Run332 legacy membership description reference is no longer present; no probe needed"
                )

            link = _find_membership_edit_link(page)
            href = str(link.get("href") or "")

            # Direct navigation only. No click is performed on the public membership card.
            page.goto(href, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1800)
            if base._looks_logged_out(page):
                raise base.NoteAuthenticationExpired("Run332 membership edit route is not authenticated")
            parsed_after = urlparse(str(page.url or ""))
            if parsed_after.scheme != "https" or parsed_after.netloc != "note.com":
                raise base.NoteDraftError(f"Run332 edit route redirected off note.com: {page.url!r}")

            surface = _surface_inventory(page)
            entries = surface.get("entries") if isinstance(surface.get("entries"), list) else []
            actions = surface.get("actions") if isinstance(surface.get("actions"), list) else []
            description_candidates = _description_candidates(entries)
            save_candidates = _save_candidates(actions)

            screenshot_written = False
            screenshot_path = os.environ.get(SCREENSHOT_ENV, "").strip()
            if screenshot_path:
                target = Path(screenshot_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(target), full_page=True)
                screenshot_written = True

            return {
                "status": "membership_description_edit_route_probed_no_mutation",
                "public_profile_url": PUBLIC_PROFILE_URL,
                "membership_name": MEMBERSHIP_NAME,
                "legacy_reference_verified": True,
                "current_onboarding_title": CURRENT_ONBOARDING_TITLE,
                "edit_link": link,
                "audited_edit_href": href,
                "url_after_direct_navigation": str(page.url or ""),
                "page_title": str(page.title() or ""),
                "description_candidates": description_candidates,
                "save_candidates": save_candidates,
                "surface_entries": entries,
                "surface_actions": actions,
                "surface_text_excerpt": str(surface.get("bodyText") or ""),
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
    result = probe()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN332_MEMBERSHIP_DESCRIPTION_EDIT_ROUTE_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
