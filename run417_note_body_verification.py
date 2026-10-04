"""Run417: install the P0-A canonical note body persistence contract.

The former distributed-anchor verifier could accept semantic corruption when a changed
value fell outside its sampled windows. Run417 now owns the deterministic canonical
renderer + reopened-DOM readback gate used by the effective draft path. Any unsupported
source/DOM or canonical mismatch fails closed with fixed, content-free errors.

Real-browser evidence on 2026-10-04 showed that note's HTML paste path flattens inline
``<code>`` into ordinary text. InlineCode therefore remains part of the offline canonical
model, but is fail-closed at the note-delivery boundary until a preserving note editor path
is proven. Fenced code blocks remain supported and exact, including whitespace.

ZERO Gemini/model calls. No public-release action.
"""
from __future__ import annotations

from typing import Any

import note_document_contract as contract
import note_document_dom as dom
import note_draft_automation as base


_ERROR = "note body canonical persistence verification failed"
_SOURCE_ERROR = "note manuscript violates the canonical document contract"
_ALLOWED_NOTE_NORMALIZATIONS = (
    contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,
    dom.NOTE_BLOCKQUOTE_FIGURE_WRAPPER,
)


def _contains_inline_code(node: Any) -> bool:
    if isinstance(node, contract.InlineCode):
        return True
    for attr in ("children", "items"):
        value = getattr(node, attr, None)
        if value and any(_contains_inline_code(child) for child in value):
            return True
    return False


def _expected_note_document(markdown_text: str) -> contract.Document:
    expected = contract.parse_presentation_markdown(markdown_text)
    expected = contract.normalize_document(expected)
    if _contains_inline_code(expected):
        raise contract.CanonicalContractError("unsupported_note_inline_code")
    return expected


def markdown_to_safe_html(markdown_text: str) -> str:
    try:
        expected = _expected_note_document(markdown_text)
        return contract.render_safe_html(expected)
    except contract.CanonicalContractError:
        raise base.NoteDraftError(_SOURCE_ERROR) from None


def verify_body_content(body: Any, manuscript: str) -> None:
    try:
        expected = _expected_note_document(manuscript)
        snapshot = dom.snapshot_note_body(body)
        actual = dom.document_from_note_snapshot(
            snapshot,
            allowed_normalizations=_ALLOWED_NOTE_NORMALIZATIONS,
        )
        receipt = contract.compare_documents(expected, actual)
    except contract.CanonicalContractError:
        raise base.NoteDraftError(_ERROR) from None
    except Exception:
        raise base.NoteDraftError(_ERROR) from None

    if receipt.get("canonical_match") is not True:
        raise base.NoteDraftError(_ERROR)


def install(note_module: Any = base) -> Any:
    note_module._markdown_to_safe_html = markdown_to_safe_html
    note_module._verify_body_content = verify_body_content
    note_module._p0a_canonical_persistence_installed = True
    note_module._run417_body_verification_installed = True
    return note_module
