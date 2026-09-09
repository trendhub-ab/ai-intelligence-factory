#!/usr/bin/env python3
"""Run316: exact, no-save probe of the member-onboarding final publish CTA.

This probe is intentionally narrower than Run315. It NEVER rewrites title/body and NEVER clicks
any final save/update/publish control. It requires the exact Run314 audited article state, enters
that article's publish settings, temporarily selects the exact AI Intelligence Factory membership
using the already-falsified Run315 helper, inventories actionable controls, then closes the browser
context without committing the publish-settings change.

ZERO model calls, ZERO Notion writes, ZERO Production ONE-SHOT.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run310_public_lp_update as run310
import run315_member_onboarding_update as run315

CONFIRM_TOKEN = "PROBE_MEMBER_ONBOARDING_FINALIZE_N284E428C80F4"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_FINALIZE_PROBE_RESULT_FILE"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _text(locator: Any) -> str:
    try:
        tag = str(locator.evaluate("el => el.tagName.toLowerCase()"))
    except Exception:
        tag = ""
    if tag in {"input", "textarea"}:
        try:
            return str(locator.input_value() or "").strip()
        except Exception:
            return ""
    try:
        return str(locator.inner_text() or "").strip()
    except Exception:
        try:
            return str(locator.text_content() or "").strip()
        except Exception:
            return ""


def _control_inventory(page: Any) -> list[dict[str, Any]]:
    script = r"""
    () => {
      const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
      };
      const inViewport = (el) => {
        const r = el.getBoundingClientRect();
        return r.bottom >= 0 && r.right >= 0 && r.top <= innerHeight && r.left <= innerWidth;
      };
      const context = (el) => {
        let cur = el;
        for (let i = 0; i < 5 && cur; i++, cur = cur.parentElement) {
          const t = norm(cur.innerText);
          if (t && t !== norm(el.innerText)) return t.slice(0, 500);
        }
        return '';
      };
      const nodes = Array.from(document.querySelectorAll(
        'button,[role="button"],input[type="submit"],input[type="button"],a[href]'
      ));
      return nodes.slice(0, 300).map((el, index) => ({
        index,
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') || '',
        type: el.getAttribute('type') || '',
        text: norm(el.innerText || el.value || ''),
        ariaLabel: el.getAttribute('aria-label') || '',
        title: el.getAttribute('title') || '',
        id: el.id || '',
        disabled: !!el.disabled,
        ariaDisabled: el.getAttribute('aria-disabled') || '',
        visible: visible(el),
        inViewport: inViewport(el),
        href: el.getAttribute('href') || '',
        context: context(el),
      }));
    }
    """
    value = page.evaluate(script)
    return value if isinstance(value, list) else []


def probe() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_FINALIZE_PROBE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run316 exact finalize-probe confirmation token is missing or invalid")

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run316") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            run315._open_editor(context, page)
            title_field = base._find_title(page)
            body = base._find_body(page, title_field)
            title = _text(title_field)
            body_text = _text(body)
            body_sha = _sha256(body_text)
            if title != run315.AUDITED_TITLE:
                raise base.NoteDraftError(f"Run316 refuses unexpected onboarding title: {title!r}")
            if body_sha != run315.AUDITED_BODY_SHA256:
                raise base.NoteDraftError("Run316 refuses onboarding body drift from exact Run314 SHA")

            run310._unique_button(page, "公開に進む").click()
            try:
                page.wait_for_url(f"**/notes/{run315.TARGET_NOTE_ID}/publish/**", timeout=15000)
            except PlaywrightTimeoutError as exc:
                raise base.NoteDraftError("Run316 did not reach exact onboarding publish settings") from exc
            if not str(page.url or "").startswith(run315.TARGET_PUBLISH_URL):
                raise base.NoteDraftError("Run316 publish URL is not the exact onboarding note")
            page.wait_for_timeout(900)

            settings_text = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
            if "記事タイプ" not in settings_text or "無料" not in settings_text or run315.MEMBERSHIP_NAME not in settings_text:
                raise base.NoteDraftError("Run316 publish settings do not match exact audited free membership surface")

            before = _control_inventory(page)
            membership = run315._ensure_membership_selected(page)
            page.wait_for_timeout(900)
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            page.wait_for_timeout(500)
            after = _control_inventory(page)
            body_after = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())

            return {
                "status": "probe_complete_no_save",
                "read_only_body": True,
                "final_commit_clicked": False,
                "zero_gemini_calls": True,
                "target_note_id": run315.TARGET_NOTE_ID,
                "source_title": title,
                "source_body_sha256": body_sha,
                "membership": membership,
                "publish_url": str(page.url or ""),
                "controls_before_membership": before,
                "controls_after_membership": after,
                "publish_text_after_membership": body_after[:16000],
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
    print("RUN316_MEMBER_ONBOARDING_FINALIZE_PROBE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
