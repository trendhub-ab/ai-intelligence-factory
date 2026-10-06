#!/usr/bin/env python3
"""Read-only hosted probe for note's private article-list DOM shape.

This one-shot recovery aid deliberately does not identify or mutate any draft.  It only
proves that the GitHub-hosted storage-state session can read ``https://note.com/notes``
and emits aggregate route shapes with private URL segments redacted.
"""
from __future__ import annotations

import base64
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import note_draft_automation as base

ARTICLE_LIST_URL = "https://note.com/notes"
RESULT_ENV = "P0B_HOSTED_DRAFT_SHAPE_RESULT_FILE"
SAFE_RESULT_KEYS = {
    "status",
    "authenticated",
    "final_route_shape",
    "anchor_route_shape_counts",
    "draft_marker_count",
    "published_marker_count",
    "visible_anchor_count",
    "zero_model_calls",
    "mutation_count",
}
_SAFE_LITERAL_SEGMENTS = {"notes", "n", "edit"}
_ALLOWED_HOSTS = {"note.com", "editor.note.com"}


def _safe_route_shape(url: str) -> str:
    """Return a query-free route family without account, note, or draft identifiers."""
    try:
        parsed = urlparse(str(url or ""))
    except Exception:
        return "{external}"
    host = str(parsed.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if host not in _ALLOWED_HOSTS:
        return "{external}"
    segments = [segment for segment in str(parsed.path or "/").split("/") if segment]
    if not segments:
        return f"{host}/"
    safe = [segment if segment in _SAFE_LITERAL_SEGMENTS else "{segment}" for segment in segments]
    return f"{host}/" + "/".join(safe)


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


def _visible_route_shapes(page: Any) -> tuple[int, dict[str, int]]:
    anchors = page.locator("a[href]")
    try:
        count = min(int(anchors.count()), 600)
    except Exception as exc:
        raise base.NoteDraftError("Could not enumerate note article-list links") from exc
    visible = 0
    route_counts: Counter[str] = Counter()
    for index in range(count):
        anchor = anchors.nth(index)
        try:
            if not anchor.is_visible(timeout=100):
                continue
            href = str(anchor.get_attribute("href") or "").strip()
        except Exception:
            continue
        if not href:
            continue
        visible += 1
        route_counts[_safe_route_shape(urljoin(ARTICLE_LIST_URL, href))] += 1
    return visible, dict(sorted(route_counts.items()))


def probe() -> dict[str, Any]:
    """Open the article list and return only aggregate, redacted, no-mutation facts."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for the hosted shape probe") from exc

    storage_state = _storage_state()
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
                    raise base.NoteAuthenticationExpired("Hosted article-list session is not authenticated")

                visible_anchor_count, route_counts = _visible_route_shapes(page)
                body_text = str(page.locator("body").inner_text(timeout=10000) or "")
                result = {
                    "status": "probe_complete_no_mutation",
                    "authenticated": True,
                    "final_route_shape": _safe_route_shape(str(page.url or "")),
                    "anchor_route_shape_counts": route_counts,
                    "draft_marker_count": body_text.count("下書き"),
                    "published_marker_count": body_text.count("公開"),
                    "visible_anchor_count": visible_anchor_count,
                    "zero_model_calls": True,
                    "mutation_count": 0,
                }
                if set(result) != SAFE_RESULT_KEYS:
                    raise base.NoteDraftError("Hosted shape probe result schema drifted")
                return result
            finally:
                context.close()
        finally:
            browser.close()


def main() -> None:
    result = probe()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("P0B_HOSTED_PRIVATE_DRAFT_SHAPE_PROBE=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
