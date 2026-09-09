#!/usr/bin/env python3
"""Run309/312: read-only audit of the exact published fixed note editor.

Run312 extends the existing exact-target Run309 audit with a read-only content snapshot so the
operator can reconcile a hand-edited public LP against the current product contract without
mutating note. The optional ``publish_settings`` stage still clicks only ``公開に進む`` and never
clicks save/update/publish confirmation controls.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud

CONFIRM_TOKEN = "AUDIT_PUBLIC_LP"
TARGET_NOTE_ID = "ned673e381ef8"
TARGET_PUBLIC_URL = f"https://note.com/trendhub_biz/n/{TARGET_NOTE_ID}"
TARGET_EDITOR_URL = f"https://editor.note.com/notes/{TARGET_NOTE_ID}/edit/"
RESULT_ENV = "NOTE_PUBLIC_LP_AUDIT_RESULT_FILE"
STAGE_ENV = "NOTE_PUBLIC_LP_AUDIT_STAGE"
ALLOWED_STAGES = {"editor", "publish_settings"}


def _field_text(locator: Any) -> str:
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
    values: list[str] = []
    for selector in ("button:visible", '[role="button"]:visible'):
        try:
            texts = page.locator(selector).all_text_contents()
        except Exception:
            continue
        for raw in texts:
            text = " ".join(str(raw or "").split())
            if text and text not in values:
                values.append(text[:120])
    return values[:80]


def _body_links(body: Any) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    try:
        anchors = body.locator("a[href]")
        count = min(anchors.count(), 80)
    except Exception:
        return values
    for idx in range(count):
        anchor = anchors.nth(idx)
        try:
            href = str(anchor.get_attribute("href") or "").strip()
            text = " ".join(str(anchor.inner_text() or "").split()).strip()
        except Exception:
            continue
        if not href:
            continue
        item = {"text": text[:160], "href": href[:1000]}
        if item not in values:
            values.append(item)
    return values


def _is_exact_editor_url(value: str) -> bool:
    text = str(value or "")
    return text.startswith("https://editor.note.com/") and TARGET_NOTE_ID in text and "/edit" in text


def _enter_publish_settings(page: Any) -> None:
    controls = page.get_by_role("button", name="公開に進む", exact=True)
    if controls.count() != 1 or not controls.first.is_visible():
        raise base.NoteDraftError("Run309 expected exactly one visible 公開に進む control")
    controls.first.click()
    page.wait_for_timeout(1200)


def audit() -> dict[str, Any]:
    if os.environ.get("NOTE_PUBLIC_LP_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run309 public LP audit confirmation token is missing or invalid")
    stage = os.environ.get(STAGE_ENV, "editor").strip() or "editor"
    if stage not in ALLOWED_STAGES:
        raise base.NoteDraftError(f"Run309 refuses unsupported audit stage: {stage}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run309 public LP editor audit") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1400)
            if not _is_exact_editor_url(str(page.url or "")):
                seeded = cloud._seed_note_state(context, page)
                if seeded:
                    page.goto(TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1400)
            if not _is_exact_editor_url(str(page.url or "")):
                raise base.NoteAuthenticationExpired(
                    "Run309 could not reach the exact authorized public note editor route"
                )

            title_field = base._find_title(page)
            body = base._find_body(page, title_field)
            title = _field_text(title_field)
            body_text = _field_text(body)
            body_links = _body_links(body)
            editor_buttons = _visible_button_texts(page)

            if stage == "publish_settings":
                _enter_publish_settings(page)

            result = {
                "status": "audit_passed",
                "read_only": True,
                "zero_gemini_calls": True,
                "public_mutation": False,
                "target_note_id": TARGET_NOTE_ID,
                "editor_url_match": True,
                "audit_stage": stage,
                "current_title": title,
                "body_visible_chars": len(body_text),
                "body_sha256": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
                "body_text": body_text,
                "body_links": body_links,
                "editor_button_texts": editor_buttons,
                "visible_button_texts": _visible_button_texts(page),
                "post_stage_url": str(page.url or ""),
            }
            return result
        finally:
            context.close()


def main() -> None:
    result = audit()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN309_PUBLIC_LP_AUDIT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
