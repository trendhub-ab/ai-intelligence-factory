#!/usr/bin/env python3
"""Read-only census for resolving one P0-B CREATION_UNKNOWN safely.

The census never opens an editor, never clicks a note card, and never writes note, Notion,
or the durable ledger. It first selects note's proven draft-list filter, then compares the
exact expected title privately against visible ``/notes/<opaque>`` cards and emits aggregate
counts only.
"""
from __future__ import annotations

import base64
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import note_draft_automation as base
import run194_note_current_contract as current
import run_p0b_hosted_private_draft_filter_navigation_probe as nav

ARTICLE_LIST_URL = "https://note.com/notes"
RESULT_ENV = "P0B_HOSTED_DRAFT_CENSUS_RESULT_FILE"
SAFE_RESULT_KEYS = {
    "status",
    "authenticated",
    "private_note_card_count",
    "exact_target_count",
    "suspicious_blank_count",
    "unreadable_count",
    "decision",
    "zero_model_calls",
    "mutation_count",
}
_PLACEHOLDER_TITLES = {
    "無題",
    "タイトル未設定",
    "タイトルなし",
    "untitled",
}
_NON_TITLE_LINES = {
    "編集",
    "公開",
    "公開中",
    "下書き",
    "予約",
    "予約投稿",
    "メニュー",
    "その他",
}
_DATEISH = re.compile(r"^(?:\d{4}[./-])?\d{1,2}[./-]\d{1,2}(?:\s+\d{1,2}:\d{2})?$")
_PRIVATE_NOTE_PATH = re.compile(r"^/notes/[^/?#]+/?$")


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value or ""))).strip()


def _classify_census(exact_target_count: int, suspicious_blank_count: int, unreadable_count: int) -> str:
    if unreadable_count > 0 or suspicious_blank_count > 0 or exact_target_count > 1:
        return "ambiguous"
    if exact_target_count == 1:
        return "single_exact"
    if exact_target_count == 0:
        return "strong_zero"
    return "ambiguous"


def _storage_state() -> dict[str, Any]:
    encoded = os.environ.get("NOTE_STORAGE_STATE_B64", "").strip()
    if not encoded:
        raise base.NoteAuthenticationExpired("NOTE_STORAGE_STATE_B64 is not configured")
    try:
        raw = base64.b64decode(encoded, validate=True)
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise base.NoteAuthenticationExpired("NOTE_STORAGE_STATE_B64 is not valid base64 JSON") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("cookies"), list):
        raise base.NoteAuthenticationExpired("note storage state has an invalid structure")
    return parsed


def _private_note_href(raw_href: str) -> str | None:
    try:
        parsed = urlparse(urljoin(ARTICLE_LIST_URL, str(raw_href or "").strip()))
    except Exception:
        return None
    host = str(parsed.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if parsed.scheme != "https" or host != "note.com" or not _PRIVATE_NOTE_PATH.match(parsed.path or ""):
        return None
    return f"https://note.com{parsed.path.rstrip('/')}"


def _card_text(anchor: Any) -> str:
    """Read only a bounded visible ancestor; never return the href itself."""
    value = anchor.evaluate(
        """el => {
            const norm = value => String(value || '').replace(/\\s+/g, ' ').trim();
            let node = el;
            let best = norm(el.innerText || el.textContent || '');
            for (let depth = 0; depth < 7 && node; depth++, node = node.parentElement) {
                const text = norm(node.innerText || node.textContent || '');
                if (text && text.length <= 3000) best = text;
                if (node.tagName === 'ARTICLE' || node.tagName === 'LI') break;
            }
            return best;
        }"""
    )
    return _normalize(value)


def _anchor_title(anchor: Any, card_text: str) -> tuple[str, bool]:
    """Return a conservative visible-title candidate and whether it is fully readable."""
    try:
        direct = _normalize(anchor.inner_text(timeout=1200))
    except Exception:
        direct = ""
    candidates: list[str] = []
    if direct:
        candidates.append(direct)
    for raw in re.split(r"[\r\n]+", str(card_text or "")):
        line = _normalize(raw)
        if line and line not in candidates:
            candidates.append(line)

    for candidate in candidates:
        lowered = candidate.lower()
        if candidate in _NON_TITLE_LINES or lowered in _PLACEHOLDER_TITLES:
            continue
        if _DATEISH.match(candidate):
            continue
        if len(candidate) < 2:
            continue
        # A truncated title cannot prove absence of the target; fail closed.
        if "…" in candidate or "..." in candidate:
            return candidate, False
        return candidate, True
    return "", False


def _expected_title(sync_id: str) -> str:
    current.install()
    prepared = current._prepare_article(sync_id)
    title = _normalize(prepared.get("title"))
    if not title:
        raise base.NoteDraftError("Expected Ready title is unavailable for census")
    return title


def census() -> dict[str, Any]:
    sync_id = base._normalize_sync_id(os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    if len(sync_id) != 32:
        raise base.NoteDraftError("Census target identity is missing or invalid")
    expected_title = _expected_title(sync_id)
    storage_state = _storage_state()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for the hosted private-draft census") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--lang=ja-JP"])
        try:
            context = browser.new_context(
                storage_state=storage_state,
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                viewport={"width": 1440, "height": 1100},
            )
            try:
                page = context.new_page()
                page.set_default_timeout(30000)
                page.goto(ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1800)
                if base._looks_logged_out(page):
                    raise base.NoteAuthenticationExpired("Hosted private-draft census session is not authenticated")

                # Use only the exact draft-filter navigation shape already proven on this
                # hosted runtime. These are UI-navigation clicks, not content mutation.
                nav.menu._open_status_filter_menu(page)
                nav._select_unique_draft_filter(page)
                if base._looks_logged_out(page):
                    raise base.NoteAuthenticationExpired("Hosted draft-filtered census session is not authenticated")

                anchors = page.locator("a[href]")
                try:
                    anchor_count = min(int(anchors.count()), 600)
                except Exception as exc:
                    raise base.NoteDraftError("Could not enumerate private article-list cards") from exc

                seen: set[str] = set()
                exact_target_count = 0
                suspicious_blank_count = 0
                unreadable_count = 0
                private_note_card_count = 0

                for index in range(anchor_count):
                    anchor = anchors.nth(index)
                    try:
                        if not anchor.is_visible(timeout=100):
                            continue
                        href = _private_note_href(str(anchor.get_attribute("href") or ""))
                    except Exception:
                        continue
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    private_note_card_count += 1
                    try:
                        card_text = _card_text(anchor)
                        title, fully_readable = _anchor_title(anchor, card_text)
                    except Exception:
                        unreadable_count += 1
                        continue
                    if not title:
                        suspicious_blank_count += 1
                        continue
                    if not fully_readable:
                        unreadable_count += 1
                        continue
                    if _normalize(title) == expected_title:
                        exact_target_count += 1

                # An empty draft-filtered result is structural drift, not proof of zero,
                # until the private-card surface itself remains observable.
                if private_note_card_count == 0:
                    unreadable_count += 1

                decision = _classify_census(
                    exact_target_count,
                    suspicious_blank_count,
                    unreadable_count,
                )
                result = {
                    "status": "census_complete_no_mutation",
                    "authenticated": True,
                    "private_note_card_count": private_note_card_count,
                    "exact_target_count": exact_target_count,
                    "suspicious_blank_count": suspicious_blank_count,
                    "unreadable_count": unreadable_count,
                    "decision": decision,
                    "zero_model_calls": True,
                    "mutation_count": 0,
                }
                if set(result) != SAFE_RESULT_KEYS:
                    raise base.NoteDraftError("Hosted census result schema drifted")
                return result
            finally:
                context.close()
        finally:
            browser.close()


def main() -> None:
    result = census()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("P0B_HOSTED_PRIVATE_DRAFT_CENSUS=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
