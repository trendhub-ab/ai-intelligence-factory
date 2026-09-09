#!/usr/bin/env python3
"""Run310: update exactly one operator-authorized published note LP.

This is NOT a general public-note publisher. It is intentionally hard-bound to the fixed sales LP
``ned673e381ef8`` and to the Run308 ready-to-paste source. The default article-publication contract
remains human-only. Run310 exists only because the operator explicitly authorized this fixed-note
maintenance operation.

Safety:
- ZERO Gemini/model calls.
- exact note ID + exact confirmation token.
- refuses an unexpected current title before mutation.
- does not change tags, magazine, membership publication settings, eyecatch, or other notes.
- uses the observed current note UI: ``公開に進む`` -> ``更新する``.
- verifies the public URL after update and fails closed on mismatch.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud

CONFIRM_TOKEN = "UPDATE_PUBLIC_LP_NED673E381EF8"
TARGET_NOTE_ID = "ned673e381ef8"
TARGET_PUBLIC_URL = f"https://note.com/trendhub_biz/n/{TARGET_NOTE_ID}"
TARGET_EDITOR_URL = f"https://editor.note.com/notes/{TARGET_NOTE_ID}/edit/"
TARGET_PUBLISH_URL = f"https://editor.note.com/notes/{TARGET_NOTE_ID}/publish/"
HANDOFF_PATH = Path("docs/reference/RUN308_PUBLIC_NOTE_READY_TO_PASTE.md")
RESULT_ENV = "NOTE_PUBLIC_LP_UPDATE_RESULT_FILE"
LEGACY_TITLE = "AIはとっても重要。でも正直、もう追いきれない。"
EXPECTED_TITLE = "「このAI、使える！」を根拠付きで判断する｜Decision Brief + AI意思決定DB"
REQUIRED_PUBLIC_MARKERS = (
    "このAI、使える！",
    "Decision Brief",
    "AI意思決定DB",
    "OfficialVendor",
    "月額1,980円",
    "使う・試す・待つ・避ける",
)


def _canon(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


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


def _load_handoff() -> tuple[str, str]:
    if not HANDOFF_PATH.is_file():
        raise base.NoteDraftError(f"Run310 handoff is missing: {HANDOFF_PATH}")
    text = HANDOFF_PATH.read_text(encoding="utf-8")
    title_match = re.search(
        r"## 1\. 公開固定note 推奨タイトル\s+\*\*(.+?)\*\*",
        text,
        flags=re.S,
    )
    body_match = re.search(
        r"## 2\. 公開固定note 完全差し替え本文\s+(.*?)\n---\n\n## 3\.",
        text,
        flags=re.S,
    )
    if not title_match or not body_match:
        raise base.NoteDraftError("Run310 could not parse the Run308 fixed-note handoff")
    title = title_match.group(1).strip()
    manuscript = body_match.group(1).strip()
    if title != EXPECTED_TITLE:
        raise base.NoteDraftError("Run310 handoff title drifted from the authorized title")
    if manuscript.startswith("# "):
        manuscript = "## " + manuscript[2:]
    if len(manuscript) < 1500:
        raise base.NoteDraftError("Run310 handoff body is unexpectedly short")
    for marker in REQUIRED_PUBLIC_MARKERS:
        if marker not in manuscript and marker not in title:
            raise base.NoteDraftError(f"Run310 handoff missing required marker: {marker}")
    if "Product Hunt" in manuscript:
        raise base.NoteDraftError("Run310 refuses a current fixed-LP body containing Product Hunt")
    if "https://note.com/trendhub_biz/membership" not in manuscript:
        raise base.NoteDraftError("Run310 membership destination is missing")
    return title, manuscript


def _is_exact_editor_url(value: str) -> bool:
    text = str(value or "")
    return text.startswith("https://editor.note.com/") and TARGET_NOTE_ID in text and "/edit" in text


def _open_exact_editor(context: Any, page: Any) -> None:
    page.goto(TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1400)
    if not _is_exact_editor_url(str(page.url or "")):
        seeded = cloud._seed_note_state(context, page)
        if seeded:
            page.goto(TARGET_EDITOR_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1400)
    if not _is_exact_editor_url(str(page.url or "")):
        raise base.NoteAuthenticationExpired("Run310 could not reach the exact authorized public note editor")


def _unique_button(page: Any, name: str) -> Any:
    """Resolve one actually-visible note button, ignoring hidden duplicate DOM controls."""
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*$")
    controls = page.locator("button:visible").filter(has_text=pattern)
    try:
        controls.first.wait_for(state="visible", timeout=10000)
    except Exception as exc:
        raise base.NoteDraftError(f"Run310 could not observe visible {name} control") from exc
    if controls.count() != 1:
        visible_texts = [
            _canon(raw)
            for raw in page.locator("button:visible").all_text_contents()
            if _canon(raw)
        ]
        matches = [text for text in visible_texts if text == name]
        if len(matches) != 1:
            raise base.NoteDraftError(
                f"Run310 expected exactly one visible {name} control; visible exact matches={len(matches)}"
            )
        controls = page.locator("button:visible").filter(has_text=pattern)
    return controls.first


def _article_text(page: Any) -> str:
    article = page.locator("article").first
    try:
        if article.is_visible(timeout=5000):
            return str(article.inner_text(timeout=10000) or "")
    except Exception:
        pass
    return str(page.locator("body").inner_text(timeout=10000) or "")


def _verify_public(page: Any, title: str) -> dict[str, Any]:
    page.goto(TARGET_PUBLIC_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1600)
    public_text = _canon(_article_text(page))
    if title not in public_text:
        full_text = _canon(str(page.locator("body").inner_text(timeout=10000) or ""))
        if title not in full_text:
            raise base.NoteDraftError("Run310 public verification could not find the new title")
    for marker in REQUIRED_PUBLIC_MARKERS:
        if marker not in public_text:
            raise base.NoteDraftError(f"Run310 public verification missing marker: {marker}")
    if LEGACY_TITLE in public_text:
        raise base.NoteDraftError("Run310 public verification still shows the legacy title")
    membership_links = page.locator('a[href*="note.com/trendhub_biz/membership"]')
    if membership_links.count() < 1:
        raise base.NoteDraftError("Run310 public verification could not find a clickable membership link")
    return {
        "public_url": TARGET_PUBLIC_URL,
        "public_markers_verified": list(REQUIRED_PUBLIC_MARKERS),
        "membership_link_verified": True,
    }


def update_public_lp() -> dict[str, Any]:
    if os.environ.get("NOTE_PUBLIC_LP_UPDATE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run310 exact public-LP update confirmation token is missing or invalid")
    title, manuscript = _load_handoff()

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run310 public LP update") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            _open_exact_editor(context, page)
            existing_title_field = base._find_title(page)
            current_title = _field_text(existing_title_field)

            if current_title == title:
                verification = _verify_public(page, title)
                return {
                    "status": "already_current",
                    "target_note_id": TARGET_NOTE_ID,
                    "public_mutation": False,
                    "zero_gemini_calls": True,
                    "title": title,
                    **verification,
                }
            if current_title != LEGACY_TITLE:
                raise base.NoteDraftError(
                    f"Run310 refuses unexpected current title: {current_title!r}"
                )

            title_field = base._set_title(page, title)
            if _field_text(title_field) != title:
                raise base.NoteDraftError("Run310 title did not persist in the editor field")
            body = base._find_body(page, title_field)
            base._paste_manuscript(page, body, manuscript)
            base._verify_body_content(body, manuscript)
            page.wait_for_timeout(1200)

            _unique_button(page, "公開に進む").click()
            try:
                page.wait_for_url(f"**/notes/{TARGET_NOTE_ID}/publish/**", timeout=15000)
            except PlaywrightTimeoutError as exc:
                raise base.NoteDraftError("Run310 did not reach the exact publish settings route") from exc
            if not str(page.url or "").startswith(TARGET_PUBLISH_URL):
                raise base.NoteDraftError("Run310 publish settings URL is not the exact authorized note")
            page.wait_for_timeout(1200)

            _unique_button(page, "更新する").click()
            page.wait_for_timeout(2200)

            verification = _verify_public(page, title)
            return {
                "status": "updated_and_verified",
                "target_note_id": TARGET_NOTE_ID,
                "public_mutation": True,
                "zero_gemini_calls": True,
                "title": title,
                "source": str(HANDOFF_PATH),
                **verification,
            }
        finally:
            context.close()


def main() -> None:
    result = update_public_lp()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN310_PUBLIC_LP_UPDATE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
