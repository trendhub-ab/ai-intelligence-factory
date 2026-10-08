"""Browser-independent note delivery compatibility contract.

This module owns only deterministic manuscript checks that can run before any browser,
model, or public mutation. The live note path currently cannot preserve inline-code
semantics, so inline code remains fail-closed until a preserving editor path is proven.
"""
from __future__ import annotations

import re
from typing import Any

import note_document_contract as contract


def _contains_inline_code(node: Any) -> bool:
    if isinstance(node, contract.InlineCode):
        return True
    for attr in ("children", "items"):
        value = getattr(node, attr, None)
        if value and any(_contains_inline_code(child) for child in value):
            return True
    return False


def expected_note_document(markdown_text: str) -> contract.Document:
    """Return the canonical document accepted by the current note delivery path."""
    expected = contract.parse_presentation_markdown(markdown_text)
    expected = contract.normalize_document(expected)
    if _contains_inline_code(expected):
        raise contract.CanonicalContractError("unsupported_note_inline_code")
    return expected


def body_manuscript_for_note(title: str, manuscript: str) -> str:
    """Mirror note's separate-title/body projection without importing browser code."""
    text = str(manuscript or "").strip()
    if not text:
        raise contract.CanonicalContractError("empty_manuscript")
    lines = text.splitlines()
    if lines and re.match(r"^#(?!#)\s+", lines[0]):
        h1 = re.sub(r"\s+", " ", re.sub(r"^#(?!#)\s+", "", lines[0])).strip()
        expected_title = re.sub(r"\s+", " ", str(title or "")).strip()
        if h1 != expected_title:
            raise contract.CanonicalContractError("title_h1_mismatch")
        text = "\n".join(lines[1:]).lstrip()
    if re.search(r"(?m)^#(?!#)\s+\S", text):
        raise contract.CanonicalContractError("unexpected_body_h1")
    return text


def require_ready_manuscript_compatible(title: str, manuscript: str) -> str:
    """Validate the exact body that would be sent to note and return it."""
    body = body_manuscript_for_note(title, manuscript)
    document = expected_note_document(body)
    contract.render_safe_html(document)
    return body


def ready_manuscript_compatible(title: str, manuscript: str) -> bool:
    try:
        require_ready_manuscript_compatible(title, manuscript)
    except contract.CanonicalContractError:
        return False
    return True
