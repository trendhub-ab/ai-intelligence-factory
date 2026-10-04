"""Install the P0-A canonical note persistence contract on the real cloud draft path.

The guard is deliberately narrow:
- approved body Markdown is parsed by the canonical contract and rendered from that tree;
- the real note body DOM is snapshotted read-only and mapped back to the same canonical model;
- any unsupported source/DOM or any canonical mismatch fails closed with a fixed, content-free error;
- the guard exposes no logging, screenshot, network, model, or publication surface.
"""
from __future__ import annotations

from typing import Any

import note_document_contract as contract
import note_document_dom as dom
import note_draft_automation as base


_ERROR = "note body canonical persistence verification failed"
_SOURCE_ERROR = "note manuscript violates the canonical document contract"
_ALLOWED_NOTE_NORMALIZATIONS = (contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,)


def markdown_to_safe_html(markdown_text: str) -> str:
    try:
        expected = contract.parse_presentation_markdown(markdown_text)
        expected = contract.normalize_document(expected)
        return contract.render_safe_html(expected)
    except contract.CanonicalContractError:
        raise base.NoteDraftError(_SOURCE_ERROR) from None


def verify_body_content(body: Any, manuscript: str) -> None:
    try:
        expected = contract.parse_presentation_markdown(manuscript)
        expected = contract.normalize_document(expected)
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
    return note_module
