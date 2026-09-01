#!/usr/bin/env python3
"""Run189 overlay: require a real note editor route before any editor DOM interaction.

Live Run188 diagnostics proved that the browser was still on note.com/ when the header-image
step ran. Run187 could accidentally accept a homepage textbox as a geometric title candidate,
so later header logic operated against the homepage instead of the editor.

This overlay makes the route itself part of the safety contract:
- enter the editor through note's visible 投稿 control first (the documented normal flow);
- use the canonical /notes/new route only as a fallback;
- never accept title/header controls unless the current URL is an editor URL;
- keep diagnostics non-content and fail closed.

Safety:
- zero Gemini/model calls;
- no public-release action;
- no cookies, storage state, article text, or private draft URL is logged.
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as base
import run187_note_editor_readiness as run187
import run188_note_header_upload_fallback as run188
import run185_note_ready_legacy_skip as run185


_ORIGINAL_RUN188_UPLOAD = run188._upload_header_image


def _safe_route_diagnostics(page: Any) -> str:
    try:
        parsed = urlparse(str(page.url or ""))
        location = f"{parsed.hostname or ''}{parsed.path or '/'}"
    except Exception:
        location = "unknown"
    try:
        post_controls = min(
            page.locator(
                'a[href*="/notes/new"], a[href="/new"], button:has-text("投稿"), '
                '[role="button"]:has-text("投稿"), a:has-text("投稿")'
            ).count(),
            99,
        )
    except Exception:
        post_controls = -1
    try:
        textboxes = min(
            page.locator(
                'textarea, input, [contenteditable="true"], '
                '[contenteditable="plaintext-only"], [role="textbox"]'
            ).count(),
            99,
        )
    except Exception:
        textboxes = -1
    return f"location={location}; post_controls={post_controls}; textboxes={textboxes}"


def _wait_editor_route(page: Any, timeout_seconds: float = 8.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if run187._is_editor_url(str(page.url or "")):
            return True
        page.wait_for_timeout(300)
    return False


def _click_post_control(page: Any) -> bool:
    selectors = [
        'a[href="/notes/new"]',
        'a[href*="/notes/new"]',
        'a[href="/new"]',
        'button:has-text("投稿")',
        '[role="button"]:has-text("投稿")',
        'a:has-text("投稿")',
    ]
    control = base._first_visible(page, selectors, timeout_ms=1400)
    if control is None:
        return False
    try:
        control.click()
        page.wait_for_timeout(500)
    except Exception:
        return False
    return _wait_editor_route(page, timeout_seconds=8.0)


def _ensure_editor_route(page: Any) -> None:
    """Reach and prove the real note editor before touching title/header controls."""
    if run187._is_editor_url(str(page.url or "")):
        return

    # The official PC flow is homepage -> 投稿 -> editor. Prefer that over guessing a
    # route because direct /new requests may redirect back to the homepage.
    try:
        if not str(page.url or "").startswith("https://note.com/"):
            page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(800)
    except Exception:
        pass

    if base._looks_logged_out(page):
        raise base.NoteAuthenticationExpired("note session has expired; refresh the storage-state secret")

    if _click_post_control(page):
        return

    # Retry once from a clean homepage in case /new left stale route/UI state.
    try:
        page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(900)
    except Exception:
        pass
    if base._looks_logged_out(page):
        raise base.NoteAuthenticationExpired("note session has expired; refresh the storage-state secret")
    if _click_post_control(page):
        return

    # Canonical route is only a final fallback. It must remain on an editor URL to count.
    try:
        page.goto("https://note.com/notes/new", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(900)
    except Exception:
        pass
    if _wait_editor_route(page, timeout_seconds=5.0):
        return

    raise base.NoteDraftError(
        "note editor route could not be established before draft mutation; "
        + _safe_route_diagnostics(page)
    )


def _find_title(page: Any) -> Any:
    _ensure_editor_route(page)
    deadline = time.time() + 18
    while time.time() < deadline:
        # Never scan a feed/homepage DOM as though it were the editor.
        if not run187._is_editor_url(str(page.url or "")):
            raise base.NoteDraftError(
                "note left the editor route while locating the title; " + _safe_route_diagnostics(page)
            )
        explicit = run187._explicit_title(page)
        if explicit is not None:
            return explicit
        ranked = run187._ranked_title(page)
        if ranked is not None:
            return ranked
        page.wait_for_timeout(500)
    raise base.NoteDraftError(
        "note title field was not found on a confirmed editor route; " + _safe_route_diagnostics(page)
    )


def _upload_header_image(page: Any, image_path: Any) -> None:
    _ensure_editor_route(page)
    _ORIGINAL_RUN188_UPLOAD(page, image_path)


def install() -> None:
    run188.install()
    base._find_title = _find_title
    base._upload_header_image = _upload_header_image


def main() -> None:
    install()
    run185.main()


if __name__ == "__main__":
    main()
