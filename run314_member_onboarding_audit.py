#!/usr/bin/env python3
"""Run314: read-only audit of the exact member onboarding note page.

Target is hard-bound to n284e428c80f4. The audit may enter publish settings to inspect
membership/publication controls, but never clicks save/update/publish confirmation controls.
ZERO model calls and ZERO note mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud

CONFIRM_TOKEN = "AUDIT_MEMBER_ONBOARDING_N284E428C80F4"
TARGET_NOTE_ID = "n284e428c80f4"
TARGET_PUBLIC_URL = f"https://note.com/trendhub_biz/n/{TARGET_NOTE_ID}"
TARGET_EDITOR_URL = f"https://editor.note.com/notes/{TARGET_NOTE_ID}/edit/"
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_AUDIT_RESULT_FILE"
STAGE_ENV = "NOTE_MEMBER_ONBOARDING_AUDIT_STAGE"
ALLOWED_STAGES = {"editor", "publish_settings"}


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


def _visible_button_texts(page: Any) -> list[str]:
    out: list[str] = []
    for selector in ("button:visible", '[role="button"]:visible'):
        try:
            values = page.locator(selector).all_text_contents()
        except Exception:
            continue
        for raw in values:
            value = " ".join(str(raw or "").split())
            if value and value not in out:
                out.append(value[:160])
    return out[:100]


def _body_links(body: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    try:
        anchors = body.locator("a[href]")
        count = min(anchors.count(), 100)
    except Exception:
        return out
    for idx in range(count):
        anchor = anchors.nth(idx)
        try:
            href = str(anchor.get_attribute("href") or "").strip()
            text = " ".join(str(anchor.inner_text() or "").split()).strip()
        except Exception:
            continue
        if href:
            item = {"text": text[:180], "href": href[:1200]}
            if item not in out:
                out.append(item)
    return out


def _visible_form_controls(page: Any) -> list[dict[str, Any]]:
    script = r"""
    () => {
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
      };
      const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
      const labelFor = (el) => {
        if (el.id) {
          const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
          if (label) return norm(label.innerText);
        }
        const parent = el.closest('label');
        if (parent) return norm(parent.innerText);
        const wrap = el.closest('[role="group"],div,li');
        return wrap ? norm(wrap.innerText).slice(0, 300) : '';
      };
      return Array.from(document.querySelectorAll('input,textarea,select,[role="radio"],[role="checkbox"],[role="switch"]'))
        .filter(visible)
        .slice(0, 120)
        .map((el) => ({
          tag: el.tagName.toLowerCase(),
          type: el.getAttribute('type') || el.getAttribute('role') || '',
          name: el.getAttribute('name') || '',
          value: el.value || el.getAttribute('value') || '',
          checked: !!el.checked || el.getAttribute('aria-checked') || '',
          label: labelFor(el),
          ariaLabel: el.getAttribute('aria-label') || '',
        }));
    }
    """
    try:
        value = page.evaluate(script)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _is_editor_url(url: str) -> bool:
    return str(url or "").startswith("https://editor.note.com/") and TARGET_NOTE_ID in str(url) and "/edit" in str(url)


def _enter_publish_settings(page: Any) -> None:
    controls = page.locator("button:visible").filter(has_text="公開に進む")
    if controls.count() < 1:
        raise base.NoteDraftError("Run314 could not find visible 公開に進む")
    exact = [i for i in range(controls.count()) if " ".join(str(controls.nth(i).inner_text() or "").split()) == "公開に進む"]
    if len(exact) != 1:
        raise base.NoteDraftError(f"Run314 expected one exact visible 公開に進む; got {len(exact)}")
    controls.nth(exact[0]).click()
    page.wait_for_timeout(1200)


def audit() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBER_ONBOARDING_AUDIT_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run314 exact audit confirmation token is missing or invalid")
    stage = os.environ.get(STAGE_ENV, "editor").strip() or "editor"
    if stage not in ALLOWED_STAGES:
        raise base.NoteDraftError(f"Run314 refuses stage: {stage}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run314") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1400)
            if not _is_editor_url(str(page.url or "")):
                seeded = cloud._seed_note_state(context, page)
                if seeded:
                    page.goto(TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1400)
            if not _is_editor_url(str(page.url or "")):
                raise base.NoteAuthenticationExpired("Run314 could not reach exact member onboarding editor")

            title_field = base._find_title(page)
            body = base._find_body(page, title_field)
            title = _text(title_field)
            body_text = _text(body)
            links = _body_links(body)
            editor_buttons = _visible_button_texts(page)
            publish_text = ""
            publish_controls: list[dict[str, Any]] = []
            if stage == "publish_settings":
                _enter_publish_settings(page)
                publish_text = "\n".join(str(page.locator("body").inner_text(timeout=10000) or "").splitlines())[:12000]
                publish_controls = _visible_form_controls(page)

            return {
                "status": "audit_passed",
                "read_only": True,
                "public_mutation": False,
                "zero_gemini_calls": True,
                "target_note_id": TARGET_NOTE_ID,
                "audit_stage": stage,
                "current_title": title,
                "body_visible_chars": len(body_text),
                "body_sha256": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
                "body_text": body_text,
                "body_links": links,
                "editor_button_texts": editor_buttons,
                "visible_button_texts": _visible_button_texts(page),
                "publish_settings_text": publish_text,
                "publish_form_controls": publish_controls,
                "post_stage_url": str(page.url or ""),
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
    print("RUN314_MEMBER_ONBOARDING_AUDIT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
