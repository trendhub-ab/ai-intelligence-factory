#!/usr/bin/env python3
"""Run187 overlay: wait for the current note editor and find its title field safely.

The live Run186 failure showed that note.com/new could be authenticated yet the editor title
control was not discoverable with the older selectors at the instant header-image handling
started. This overlay keeps the existing fail-closed contract while adding:
- editor-readiness retries;
- the canonical /notes/new route when /new has not settled there;
- a safe fallback through note's visible 投稿 control;
- semantic + geometry based title-field discovery for current editor markup;
- non-content diagnostics only when discovery ultimately fails.

Safety:
- zero Gemini/model calls;
- no public-release action;
- no article text, cookies, URLs with credentials, or storage-state content are logged;
- ambiguous editables remain fail-closed.
"""
from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as base
import run186_note_header_image_resilience as run186


_TITLE_WORD_RE = re.compile(r"(?:記事)?タイトル|title", re.I)
_EDITOR_PATH_RE = re.compile(r"^/notes/(?:new|[^/]+/edit)/?$", re.I)


def _attribute_blob(locator: Any) -> str:
    values: list[str] = []
    for attr in (
        "placeholder",
        "aria-label",
        "aria-placeholder",
        "data-placeholder",
        "data-testid",
        "name",
        "role",
    ):
        try:
            value = locator.get_attribute(attr)
        except Exception:
            value = None
        if value:
            values.append(str(value))
    return " ".join(values)


def _title_candidate_score(*, attrs: str, tag: str, y: float, height: float, editable: bool) -> tuple[int, float] | None:
    """Rank only plausible title controls; lower tuples are better."""
    attrs = str(attrs or "")
    tag = str(tag or "").lower()
    if _TITLE_WORD_RE.search(attrs):
        return (0, y)
    if y < 0 or y > 820:
        return None
    if height <= 0 or height > 220:
        return None
    if tag in {"textarea", "input"}:
        return (2, y)
    if editable:
        return (4, y)
    return None


def _is_editor_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or ""))
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    if host not in {"note.com", "www.note.com", "editor.note.com"}:
        return False
    return bool(_EDITOR_PATH_RE.match(parsed.path or "/"))


def _ranked_title(page: Any) -> Any | None:
    selectors = (
        'textarea, input, [contenteditable="true"], [contenteditable="plaintext-only"], [role="textbox"]'
    )
    locator = page.locator(selectors)
    ranked: list[tuple[int, float, Any]] = []
    seen: set[str] = set()
    try:
        count = min(locator.count(), 40)
    except Exception:
        count = 0

    for index in range(count):
        item = locator.nth(index)
        try:
            if not item.is_visible(timeout=350):
                continue
            box = item.bounding_box()
            if not box:
                continue
            tag = str(item.evaluate("el => el.tagName.toLowerCase()"))
            editable_attr = str(item.get_attribute("contenteditable") or "").lower()
            editable = editable_attr in {"true", "plaintext-only"}
            attrs = _attribute_blob(item)
            score = _title_candidate_score(
                attrs=attrs,
                tag=tag,
                y=float(box.get("y", -1)),
                height=float(box.get("height", 0)),
                editable=editable,
            )
            if score is None:
                continue
            identity = f"{tag}:{round(float(box.get('x', 0)), 1)}:{round(float(box.get('y', 0)), 1)}"
            if identity in seen:
                continue
            seen.add(identity)
            ranked.append((score[0], score[1], item))
        except Exception:
            continue

    if not ranked:
        return None
    ranked.sort(key=lambda row: (row[0], row[1]))

    # Fail closed if the best two purely geometric candidates are effectively tied.
    if len(ranked) >= 2 and ranked[0][0] >= 2 and ranked[1][0] == ranked[0][0]:
        if abs(ranked[1][1] - ranked[0][1]) < 8:
            return None
    return ranked[0][2]


def _explicit_title(page: Any) -> Any | None:
    selectors = [
        'textarea[placeholder*="タイトル"]',
        'input[placeholder*="タイトル"]',
        '[data-testid*="title" i]',
        '[aria-label*="タイトル"]',
        '[aria-placeholder*="タイトル"]',
        '[data-placeholder*="タイトル"]',
        '[role="textbox"][aria-label*="タイトル"]',
        '[role="textbox"][data-placeholder*="タイトル"]',
        'h1[contenteditable="true"]',
        'h1[contenteditable="plaintext-only"]',
    ]
    return base._first_visible(page, selectors, timeout_ms=700)


def _try_enter_editor(page: Any) -> None:
    current = str(page.url or "")
    if _is_editor_url(current):
        return

    # note.com/new is documented to resolve to /notes/new. Use that canonical route first.
    try:
        page.goto("https://note.com/notes/new", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1200)
    except Exception:
        pass
    if _is_editor_url(str(page.url or "")):
        return

    # Current official help also supports entering the editor through the visible 投稿 control.
    try:
        page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(900)
    except Exception:
        return

    post = base._first_visible(
        page,
        [
            'a[href="/notes/new"]',
            'a[href*="/notes/new"]',
            'button:has-text("投稿")',
            '[role="button"]:has-text("投稿")',
            'a:has-text("投稿")',
        ],
        timeout_ms=1200,
    )
    if post is None:
        return
    try:
        post.click()
        page.wait_for_timeout(1400)
    except Exception:
        return


def _safe_editor_diagnostics(page: Any) -> str:
    try:
        parsed = urlparse(str(page.url or ""))
        location = f"{parsed.hostname or ''}{parsed.path or '/'}"
    except Exception:
        location = "unknown"
    counts: list[str] = []
    for label, selector in (
        ("input", "input"),
        ("textarea", "textarea"),
        ("editable", '[contenteditable="true"], [contenteditable="plaintext-only"]'),
        ("textbox", '[role="textbox"]'),
        ("button", "button"),
    ):
        try:
            counts.append(f"{label}={min(page.locator(selector).count(), 99)}")
        except Exception:
            counts.append(f"{label}=?")
    return f"location={location}; " + ", ".join(counts)


def _find_title(page: Any) -> Any:
    deadline = time.time() + 22
    attempted_entry = False
    while time.time() < deadline:
        explicit = _explicit_title(page)
        if explicit is not None:
            return explicit
        ranked = _ranked_title(page)
        if ranked is not None:
            return ranked

        if not attempted_entry and time.time() + 14 < deadline:
            attempted_entry = True
            _try_enter_editor(page)
        else:
            page.wait_for_timeout(650)

    raise base.NoteDraftError(
        "note title field was not found after editor-readiness retry; " + _safe_editor_diagnostics(page)
    )


def install() -> None:
    # Run186 resolves base._find_title dynamically, so this also fixes its header-zone lookup.
    base._find_title = _find_title


def main() -> None:
    install()
    run186.main()


if __name__ == "__main__":
    main()
