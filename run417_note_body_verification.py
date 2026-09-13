"""Run417: verify note body insertion using distributed manuscript anchors.

The note editor keeps the document title in a separate title field and may omit a pasted
leading Markdown H1 from the body surface. Verification therefore must not depend on the
first 32 manuscript characters. It still fails closed unless substantial body text and
multiple distributed anchors survive insertion.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

import note_draft_automation as base


def _visible_body_source(manuscript: str) -> str:
    text = str(manuscript or "").replace("\r\n", "\n").replace("\r", "\n")
    # note already has a separate title field. Ignore exactly one leading Markdown H1 only.
    text = re.sub(r"^\s*#\s+[^\n]+(?:\n+|$)", "", text, count=1)
    return base._plain_manuscript_text(text)


def _normalize_visible_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _anchors(expected: str, *, width: int = 24) -> list[str]:
    text = _normalize_visible_text(expected)
    if len(text) < width:
        return [text] if text else []
    # Three distributed windows make partial insertion much harder to pass than the old
    # prefix-only check while tolerating note's title/body separation.
    starts = [0, max(0, (len(text) - width) // 2), max(0, len(text) - width)]
    out: list[str] = []
    for start in starts:
        chunk = text[start : start + width].strip()
        if len(chunk) >= 12 and chunk not in out:
            out.append(chunk)
    return out


def verify_body_content(body: Any, manuscript: str) -> None:
    expected = _normalize_visible_text(_visible_body_source(manuscript))
    try:
        actual = _normalize_visible_text(str(body.inner_text(timeout=5000) or ""))
    except Exception as exc:
        raise base.NoteDraftError("Could not read note body after insertion") from exc
    if not expected:
        raise base.NoteDraftError("Prepared manuscript has no visible body text")

    # Keep a meaningful absolute + proportional floor, but account for editor-only removal
    # of the leading H1. This is not a generic non-empty-body acceptance rule.
    minimum = min(240, max(80, len(expected) // 8))
    anchors = _anchors(expected)
    matched = sum(1 for anchor in anchors if anchor in actual)
    required = min(2, len(anchors))
    if len(actual) < minimum or matched < required:
        raise base.NoteDraftError(
            "note body insertion verification failed; refusing to save a malformed draft"
        )


def install(note_module: Any = base) -> Any:
    note_module._verify_body_content = verify_body_content
    note_module._run417_body_verification_installed = True
    return note_module
