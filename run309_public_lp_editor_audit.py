#!/usr/bin/env python3
"""Run309: read-only audit of the exact published fixed note editor.

This is a zero-model, zero-mutation browser probe for one explicitly authorized public note.
It exists only to observe the current note.com editor controls before any public-page update is
implemented. It never changes title/body, never clicks save/update/publish controls, and never
opens a generic article target.
"""
from __future__ import annotations

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


def _is_exact_editor_url(value: str) -> bool:
    text = str(value or "")
    return text.startswith("https://editor.note.com/") and TARGET_NOTE_ID in text and "/edit" in text


def audit() -> dict[str, Any]:
    if os.environ.get("NOTE_PUBLIC_LP_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run309 public LP audit confirmation token is missing or invalid")

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
            result = {
                "status": "audit_passed",
                "read_only": True,
                "zero_gemini_calls": True,
                "public_mutation": False,
                "target_note_id": TARGET_NOTE_ID,
                "editor_url_match": True,
                "current_title": title,
                "body_visible_chars": len(body_text),
                "visible_button_texts": _visible_button_texts(page),
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
