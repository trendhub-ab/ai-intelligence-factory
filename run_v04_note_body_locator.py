"""v0.4-only safe body editor discovery on an already verified note editor.

The legacy finder recognizes just div[contenteditable="true"] and may reject
a current note editor without identifying which step failed. This is a bounded
selector fallback, not a generalized arbitrary-DOM click or content reader.

No text, private URLs, HTML, element attributes, or form values are logged.
Ambiguous/hidden/above-title controls fail closed instead of pasting.
"""
from __future__ import annotations

import re
from typing import Any

import note_draft_automation as base
import run187_note_editor_readiness as readiness

_EDITOR_SELECTOR = ", ".join((
    '[contenteditable="true"]',
    '[contenteditable="plaintext-only"]',
    '[contenteditable=""]',
    '[role="textbox"][data-placeholder]',
    '[role="textbox"][aria-label]',
    'textarea[aria-label*="本文"]',
    'textarea[placeholder*="本文"]',
))
_BODY_HINT = re.compile(r"本文|body|article.?content|prosemirror|tiptap|lexical", re.I)
_TITLE_HINT = re.compile(r"タイトル|title", re.I)


def _candidate(item: Any, title_bottom: float) -> tuple[int, tuple[int, ...], Any] | None:
    try:
        if not item.is_visible(timeout=350):
            return None
        box = item.bounding_box()
        if not isinstance(box, dict):
            return None
        x = float(box.get("x", -1))
        y = float(box.get("y", -1))
        width = float(box.get("width", 0))
        height = float(box.get("height", 0))
        # Require a visible, nontrivial editor entirely below the title field.
        if x < 0 or y < max(0, title_bottom + 8) or width < 120 or height < 8:
            return None
        tag = str(item.evaluate("el => el.tagName.toLowerCase()")).lower()
        if tag in {"h1", "input"}:
            return None
        editable = str(item.get_attribute("contenteditable") or "").lower()
        if editable not in {"true", "plaintext-only", ""} or (
            editable == "" and tag != "textarea"
            and item.get_attribute("contenteditable") is None
        ):
            return None
        attrs = " ".join(
            str(item.get_attribute(key) or "")[:160]
            for key in ("aria-label", "aria-placeholder", "data-placeholder",
                        "data-testid", "class", "id", "role")
        )
        # Reject potential title controls, even if geometrically lower.
        if _TITLE_HINT.search(attrs):
            return None
        # A container with nested editables is not itself the edit target.
        has_nested = item.evaluate(
            "el => !!el.querySelector('[contenteditable=true],"
            "[contenteditable=plaintext-only]')"
        )
        if has_nested:
            return None
        score = 0 if _BODY_HINT.search(attrs) else 1
        geometry = (round(x), round(y), round(width), round(height))
        return (score, geometry, item)
    except Exception:
        return None


def find_body(page: Any, title_field: Any | None = None) -> Any:
    """Find exactly one visible body editable on a verified note editor route."""
    if not readiness._is_editor_url(str(page.url or "")):
        raise base.NoteDraftError("V04_NOTE_BODY_EDITOR_ROUTE_UNVERIFIED")
    try:
        box = title_field.bounding_box() if title_field is not None else None
        if not isinstance(box, dict):
            raise ValueError("title bounding box unavailable")
        title_bottom = float(box["y"]) + float(box["height"])
        if title_bottom < 0:
            raise ValueError("title geometry invalid")
    except Exception:
        raise base.NoteDraftError("V04_NOTE_BODY_TITLE_GEOMETRY_INVALID") from None

    for _ in range(8):
        try:
            locator = page.locator(_EDITOR_SELECTOR)
            count = min(locator.count(), 60)
        except Exception:
            count = 0
        candidates = []
        seen = set()
        for index in range(count):
            item = locator.nth(index)
            result = _candidate(item, title_bottom)
            if result is None:
                continue
            rank, geometry, target = result
            if geometry in seen:
                continue
            seen.add(geometry)
            candidates.append((rank, geometry, target))
        if candidates:
            # An explicit body editor beats a generic editable. Within the
            # selected rank, exactly one node must exist or we refuse to paste.
            best_rank = min(item[0] for item in candidates)
            best = [item for item in candidates if item[0] == best_rank]
            if len(best) != 1:
                raise base.NoteDraftError("V04_NOTE_BODY_EDITOR_AMBIGUOUS")
            return best[0][2]
        page.wait_for_timeout(400)
    raise base.NoteDraftError("V04_NOTE_BODY_EDITOR_NOT_FOUND")
