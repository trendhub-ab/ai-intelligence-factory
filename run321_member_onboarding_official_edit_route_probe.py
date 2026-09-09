#!/usr/bin/env python3
"""Run321: probe note's official existing-article edit -> publish-settings route.

Run318 opened the editor URL directly and observed no final update CTA. note's current official
help instead prescribes `自分の記事 -> ... -> 編集 -> 公開に進む -> 更新する` for editing an
already-published article. Run321 reproduces that navigation exactly in a fresh cookie-only
browser and inventories the resulting editor/publish controls. It may choose the exact
`最新の下書き` navigation option if note presents a version-choice dialog, but it never changes
article content/settings and never clicks any final update/publish control.
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

CONFIRM_TOKEN = "PROBE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_N284E428C80F4_SHAAAB9E57B"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_PROBE_RESULT_FILE"
EDIT_LABEL = "編集"
LATEST_DRAFT_LABEL = "最新の下書き"


def _visible_exact(page: Any, *, role: str, name: str) -> Any:
    loc = page.get_by_role(role, name=name, exact=True)
    visible: list[Any] = []
    for idx in range(loc.count()):
        item = loc.nth(idx)
        try:
            if item.is_visible():
                visible.append(item)
        except Exception:
            pass
    if len(visible) != 1:
        raise base.NoteDraftError(f"Run321 expected one exact visible {role} {name!r}; got {len(visible)}")
    return visible[0]


def _dom_action_inventory(page: Any) -> list[dict[str, Any]]:
    script = r"""
    () => {
      const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
      };
      const nodes = Array.from(document.querySelectorAll(
        'button,[role="button"],[role="menuitem"],input[type="submit"],input[type="button"],a[href]'
      ));
      return nodes.slice(0, 450).map((el, index) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return {
          index,
          tag: el.tagName.toLowerCase(),
          role: el.getAttribute('role') || '',
          type: el.getAttribute('type') || '',
          text: norm(el.innerText || el.value || ''),
          ariaLabel: el.getAttribute('aria-label') || '',
          title: el.getAttribute('title') || '',
          disabled: !!el.disabled,
          ariaDisabled: el.getAttribute('aria-disabled') || '',
          visible: visible(el),
          display: s.display,
          visibility: s.visibility,
          position: s.position,
          top: r.top,
          bottom: r.bottom,
          href: el.getAttribute('href') || '',
        };
      });
    }
    """
    value = page.evaluate(script)
    return value if isinstance(value, list) else []


def _snapshot(page: Any) -> dict[str, Any]:
    text = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
    dialogs: list[str] = []
    d = page.locator('[role="dialog"]')
    for idx in range(min(d.count(), 20)):
        item = d.nth(idx)
        try:
            if item.is_visible():
                dialogs.append(" ".join(str(item.inner_text() or "").split())[:8000])
        except Exception:
            pass
    return {
        "url": str(page.url or ""),
        "body_text": text[:22000],
        "dialogs": dialogs,
        "visible_controls": run316._control_inventory(page),
        "all_actionables": _dom_action_inventory(page),
    }


def _commit_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {"更新する", "更新", "公開する", "公開", "投稿する", "投稿", "保存する", "保存"}
    out: list[dict[str, Any]] = []
    for row in rows:
        values = {
            str(row.get("text") or "").strip(),
            str(row.get("ariaLabel") or "").strip(),
            str(row.get("title") or "").strip(),
        }
        if values & labels:
            out.append(row)
    return out


def _maybe_choose_latest_draft(page: Any) -> dict[str, Any]:
    body = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
    prompt_present = "公開した時点の記事" in body or LATEST_DRAFT_LABEL in body
    if not prompt_present:
        return {"prompt_present": False, "latest_choice_clicked": False}
    latest = page.get_by_text(LATEST_DRAFT_LABEL, exact=True)
    visible: list[Any] = []
    for idx in range(latest.count()):
        item = latest.nth(idx)
        try:
            if item.is_visible():
                visible.append(item)
        except Exception:
            pass
    if len(visible) != 1:
        raise base.NoteDraftError(f"Run321 version-choice prompt present but exact latest draft choice count={len(visible)}")
    visible[0].click()
    page.wait_for_timeout(1000)
    return {"prompt_present": True, "latest_choice_clicked": True}


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run321 exact official-edit-route probe confirmation is missing or invalid")

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run321") from exc

    with sync_playwright() as playwright:
        cookies = run318._cookie_source(playwright)
        browser = run317._launch_clean_browser(playwright)
        try:
            context = run317._new_cookie_only_context(browser, cookies)
            try:
                page = context.new_page()
                page.set_default_timeout(30000)

                # Independent server-state proof before navigating through the official list route.
                _, body, title, body_text = run317._open_exact_clean_editor(page)
                body_sha = run315._sha256(body_text)
                if title != run315.NEW_TITLE or body_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run321 refuses non-server-saved source state: title={title!r} sha256={body_sha}"
                    )
                run315._verify_editor(body)

                page.goto(run319.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1600)
                card = run319._mark_target_card(page)
                if not card.get("cardFound"):
                    raise base.NoteDraftError("Run321 exact target article card was not found")
                menu = run319._open_menu_if_exact(page, card)
                if not menu.get("opened"):
                    raise base.NoteDraftError(f"Run321 exact target menu did not open: {menu}")
                _visible_exact(page, role="menuitem", name=EDIT_LABEL).click()
                page.wait_for_timeout(1200)

                route_snapshot_before_choice = _snapshot(page)
                version_choice = _maybe_choose_latest_draft(page)
                if version_choice.get("latest_choice_clicked"):
                    page.wait_for_timeout(800)

                if not run315._is_exact_editor(str(page.url or "")):
                    raise base.NoteDraftError(f"Run321 official 編集 route did not reach exact editor: {page.url}")
                title_field = base._find_title(page)
                body = base._find_body(page, title_field)
                routed_title = run315._field_text(title_field)
                routed_body_text = run315._body_text(body)
                routed_sha = run315._sha256(routed_body_text)
                if routed_title != run315.NEW_TITLE or routed_sha != run317.NEW_BODY_SHA256:
                    raise base.NoteDraftError(
                        f"Run321 official edit route did not expose exact latest draft: title={routed_title!r} sha256={routed_sha}"
                    )
                run315._verify_editor(body)
                editor_snapshot = _snapshot(page)

                run310._unique_button(page, "公開に進む").click()
                try:
                    page.wait_for_url(f"**/notes/{run315.TARGET_NOTE_ID}/publish/**", timeout=15000)
                except PlaywrightTimeoutError as exc:
                    raise base.NoteDraftError("Run321 official route did not reach exact publish settings") from exc
                if not str(page.url or "").startswith(run315.TARGET_PUBLISH_URL):
                    raise base.NoteDraftError("Run321 publish-settings URL drifted from exact target")
                page.wait_for_timeout(1200)

                publish_snapshot = _snapshot(page)
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(400)
                publish_bottom_snapshot = _snapshot(page)
                all_rows = publish_snapshot["all_actionables"] + publish_bottom_snapshot["all_actionables"]
                commit_candidates = _commit_candidates(all_rows)

                return {
                    "status": "probe_complete_no_public_mutation",
                    "target_note_id": run315.TARGET_NOTE_ID,
                    "source_title": title,
                    "source_body_sha256": body_sha,
                    "fresh_cookie_only_context": True,
                    "local_storage_seeded": False,
                    "article_list_card": card,
                    "article_list_menu": menu,
                    "edit_menu_clicked": True,
                    "route_snapshot_before_version_choice": route_snapshot_before_choice,
                    "version_choice": version_choice,
                    "routed_title": routed_title,
                    "routed_body_sha256": routed_sha,
                    "editor_snapshot": editor_snapshot,
                    "publish_snapshot": publish_snapshot,
                    "publish_bottom_snapshot": publish_bottom_snapshot,
                    "candidate_commit_controls": commit_candidates,
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
    print("RUN321_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
