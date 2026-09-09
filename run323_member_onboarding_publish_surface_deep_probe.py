#!/usr/bin/env python3
"""Run323: deeply inspect note publish settings without committing anything.

Run322 proved the exact existing-article latest-draft route reaches the target publish-settings
URL, but no final `更新する` control appeared in the ordinary actionable inventory even though
note's current help documents that control. Run323 follows the exact Run322 route, then inspects
forms, hidden/disabled controls, sticky/fixed layers, broad interactive nodes, and text/attribute
matches at several settle times and viewport positions. It never edits settings or clicks a final
save/update/publish control.
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

CONFIRM_TOKEN = run321.CONFIRM_TOKEN
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_PUBLISH_SURFACE_DEEP_PROBE_RESULT_FILE"
SCREENSHOT_ENV = "NOTE_MEMBER_ONBOARDING_PUBLISH_SURFACE_SCREENSHOT_FILE"


def _deep_surface(page: Any, label: str) -> dict[str, Any]:
    script = r"""
    (label) => {
      const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
      const textOf = (el) => norm(el.innerText || el.textContent || el.value || '');
      const rect = (el) => {
        const r = el.getBoundingClientRect();
        return {left:r.left, top:r.top, right:r.right, bottom:r.bottom, width:r.width, height:r.height};
      };
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
      };
      const contextText = (el) => {
        let cur = el;
        const out = [];
        for (let i = 0; i < 4 && cur; i++, cur = cur.parentElement) {
          const t = textOf(cur);
          if (t && !out.includes(t)) out.push(t.slice(0, 900));
        }
        return out;
      };
      const attrs = (el) => {
        const out = {};
        for (const a of Array.from(el.attributes || [])) {
          if (/^(aria-|data-|type$|name$|value$|title$|href$|class$|id$|role$|tabindex$)/i.test(a.name)) {
            out[a.name] = String(a.value || '').slice(0, 900);
          }
        }
        return out;
      };
      const nodeRow = (el, index) => {
        const s = getComputedStyle(el);
        return {
          index,
          tag: el.tagName.toLowerCase(),
          text: textOf(el).slice(0, 1800),
          visible: visible(el),
          disabled: !!el.disabled,
          checked: typeof el.checked === 'boolean' ? el.checked : null,
          position: s.position,
          display: s.display,
          visibility: s.visibility,
          opacity: s.opacity,
          zIndex: s.zIndex,
          cursor: s.cursor,
          rect: rect(el),
          attrs: attrs(el),
          context: contextText(el),
        };
      };

      const broadSelector = [
        'button','input','select','textarea','a[href]','summary',
        '[role]','[tabindex]','[onclick]','[contenteditable="true"]',
        '[data-testid]','[data-test-id]'
      ].join(',');
      const broad = Array.from(document.querySelectorAll(broadSelector)).slice(0, 1200);
      const broadRows = broad.map(nodeRow);

      const keyword = /(更新する|更新|公開する|公開|投稿する|投稿|保存する|保存|submit|publish|update|save)/i;
      const keywordRows = broadRows.filter((row) => {
        const blob = [row.text, JSON.stringify(row.attrs), ...(row.context || [])].join(' ');
        return keyword.test(blob);
      }).slice(0, 300);

      const all = Array.from(document.querySelectorAll('*'));
      const fixedSticky = all.filter((el) => {
        const p = getComputedStyle(el).position;
        return p === 'fixed' || p === 'sticky';
      }).slice(0, 300).map(nodeRow);

      const forms = Array.from(document.forms).slice(0, 50).map((form, index) => ({
        index,
        action: form.getAttribute('action') || '',
        method: form.getAttribute('method') || '',
        id: form.id || '',
        className: String(form.className || ''),
        text: textOf(form).slice(0, 4000),
        rect: rect(form),
        visible: visible(form),
        controls: Array.from(form.querySelectorAll('button,input,select,textarea,[role="button"]')).slice(0, 200).map(nodeRow),
      }));

      const bodyInner = norm(document.body ? document.body.innerText : '');
      const bodyText = norm(document.body ? document.body.textContent : '');
      const html = document.documentElement ? document.documentElement.outerHTML : '';
      const needles = ['更新する','更新','公開する','投稿する','保存する','publish','update','save'];
      const matches = {};
      for (const needle of needles) {
        const esc = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const re = new RegExp(esc, /[A-Za-z]/.test(needle) ? 'gi' : 'g');
        matches[needle] = {
          innerText: (bodyInner.match(re) || []).length,
          textContent: (bodyText.match(re) || []).length,
          outerHTML: (html.match(re) || []).length,
        };
      }

      return {
        label,
        url: location.href,
        title: document.title,
        readyState: document.readyState,
        viewport: {width: innerWidth, height: innerHeight, devicePixelRatio: devicePixelRatio},
        scroll: {
          x: scrollX, y: scrollY,
          documentHeight: Math.max(document.body?.scrollHeight || 0, document.documentElement?.scrollHeight || 0),
          documentWidth: Math.max(document.body?.scrollWidth || 0, document.documentElement?.scrollWidth || 0),
        },
        bodyInnerText: bodyInner.slice(0, 30000),
        keywordMatches: matches,
        keywordRows,
        forms,
        fixedSticky,
        broadCount: broadRows.length,
        visibleBroadCount: broadRows.filter(r => r.visible).length,
        hiddenOrDisabledBroad: broadRows.filter(r => !r.visible || r.disabled).slice(0, 400),
      };
    }
    """
    value = page.evaluate(script, label)
    return value if isinstance(value, dict) else {"label": label, "error": "non-dict snapshot"}


def _candidate_labels(snapshot: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for row in snapshot.get("keywordRows") or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        attrs = row.get("attrs") if isinstance(row.get("attrs"), dict) else {}
        values = [text, str(attrs.get("aria-label") or ""), str(attrs.get("title") or ""), str(attrs.get("value") or "")]
        for value in values:
            value = value.strip()
            if value and value not in out:
                out.append(value[:500])
    return out[:120]


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_PUBLISH_SURFACE_DEEP_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run323 exact deep publish-surface confirmation is missing or invalid")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run323") from exc

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

                # Re-prove exact server-saved source state.
                _, body, source_title, source_body_text = run317._open_exact_clean_editor(page)
                source_sha = run315._sha256(source_body_text)
                if source_title != run315.NEW_TITLE or source_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run323 refuses non-server-saved source state: title={source_title!r} sha256={source_sha}"
                    )
                run315._verify_editor(body)

                # Follow the exact Run321b/Run322-proven existing-article route.
                page.goto(run319.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1600)
                card = run319._mark_target_card(page)
                if not card.get("cardFound"):
                    raise base.NoteDraftError("Run323 exact target article card was not found")
                menu = run319._open_menu_if_exact(page, card)
                if not menu.get("opened"):
                    raise base.NoteDraftError(f"Run323 exact target menu did not open: {menu}")
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
                        f"Run323 routed revision mismatch: title={routed_title!r} sha256={routed_sha}"
                    )
                run315._verify_editor(body)

                run310._unique_button(page, "公開に進む").click()
                try:
                    page.wait_for_url(f"**/notes/{run315.TARGET_NOTE_ID}/publish/**", timeout=15000)
                except Exception as exc:
                    raise base.NoteDraftError("Run323 did not reach exact publish settings") from exc
                if not str(page.url or "").startswith(run315.TARGET_PUBLISH_URL):
                    raise base.NoteDraftError(f"Run323 publish URL drifted: {page.url}")

                snapshots: list[dict[str, Any]] = []
                page.wait_for_timeout(1000)
                page.evaluate("window.scrollTo(0,0)")
                snapshots.append(_deep_surface(page, "top_t1s"))
                page.wait_for_timeout(2000)
                snapshots.append(_deep_surface(page, "top_t3s"))
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(1200)
                snapshots.append(_deep_surface(page, "bottom_t4s"))
                page.wait_for_timeout(4000)
                snapshots.append(_deep_surface(page, "bottom_t8s"))
                page.evaluate("window.scrollTo(0,0)")
                page.wait_for_timeout(500)
                snapshots.append(_deep_surface(page, "top_final"))

                screenshot_file = os.environ.get(SCREENSHOT_ENV, "").strip()
                if screenshot_file:
                    path = Path(screenshot_file)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(path), full_page=True)

                labels: list[str] = []
                for snap in snapshots:
                    for label in _candidate_labels(snap):
                        if label not in labels:
                            labels.append(label)

                exact_update_text_hits = sum(
                    int(((snap.get("keywordMatches") or {}).get("更新する") or {}).get("outerHTML") or 0)
                    for snap in snapshots
                )
                return {
                    "status": "deep_probe_complete_no_public_mutation",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": source_title,
                    "source_body_sha256": source_sha,
                    "routed_title": routed_title,
                    "routed_body_sha256": routed_sha,
                    "version_route": version_route,
                    "publish_url": str(page.url or ""),
                    "snapshots": snapshots,
                    "candidate_labels": labels[:200],
                    "exact_update_outerhtml_hits_across_snapshots": exact_update_text_hits,
                    "screenshot_written": bool(screenshot_file),
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
    print("RUN323_MEMBER_ONBOARDING_PUBLISH_SURFACE_DEEP_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
