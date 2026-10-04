#!/usr/bin/env python3
"""Ephemeral insertion-only structural diagnosis for P0-A canonical note DOM mapping.

Creates a fresh private editor surface, sets a synthetic title, pastes only the synthetic
proof fixture, snapshots the resulting editor DOM, and closes the browser without invoking
save, publication, Notion, model, screenshot, or queue mutation surfaces. Output is limited
to structural counts/categorical canonical mismatch information and a boolean indicating
whether note exposed a stable edit route before any save action.
"""
from __future__ import annotations

import json
from typing import Any

import note_document_contract as contract
import note_document_dom as dom
import note_draft_automation as base
import p0a_b2_private_browser_proof as proof
import run187_note_editor_readiness as run187
import run190_note_persistent_cloud as cloud
import run222_note_presentation_integrity as run222
import run417_note_body_verification as run417


def _node_counts(document: contract.Document) -> dict[str, int]:
    counts: dict[str, int] = {}

    def walk(node: Any) -> None:
        name = type(node).__name__
        counts[name] = counts.get(name, 0) + 1
        for attr in ("children", "items"):
            value = getattr(node, attr, None)
            if value:
                for child in value:
                    walk(child)

    walk(document)
    return dict(sorted(counts.items()))


def run() -> dict[str, object]:
    cloud.install()
    manuscript = run222.prepare_note_editor_manuscript(proof.FIXTURE_SOURCE, proof.FIXTURE_TITLE)
    expected = contract.parse_presentation_markdown(manuscript)

    result: dict[str, object] = {
        "status": "ephemeral_insertion_diagnostic_complete",
        "zero_gemini_calls": True,
        "notion_access": False,
        "public_release": False,
        "save_invoked": False,
        "expected_node_counts": _node_counts(expected),
        "dom_normalization_policy_version": dom.DOM_NORMALIZATION_POLICY_VERSION,
        "normalization_codes": [
            contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,
            dom.NOTE_BLOCKQUOTE_FIGURE_WRAPPER,
        ],
    }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            cloud._establish_editor(page, context)
            if not run187._is_editor_url(str(page.url or "")):
                raise RuntimeError("private editor route was not established")

            title_field = base._set_title(page, proof.FIXTURE_TITLE)
            body = base._find_body(page, title_field)
            base._paste_manuscript(page, body, manuscript)
            body = base._find_body(page, title_field)

            current_url = str(page.url or "")
            result["stable_route_observed_before_save"] = bool(
                "/notes/" in current_url and current_url.rstrip("/").endswith("/edit")
            )

            snapshot = dom.snapshot_note_body(body)
            result.update(dom.safe_snapshot_diagnostics(snapshot))
            try:
                actual = dom.document_from_note_snapshot(
                    snapshot,
                    allowed_normalizations=(
                        contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,
                        dom.NOTE_BLOCKQUOTE_FIGURE_WRAPPER,
                    ),
                )
            except contract.CanonicalContractError as exc:
                result["canonical_actual_supported"] = False
                result["canonical_diagnostic_code"] = exc.code
                return result

            receipt = contract.compare_documents(expected, actual)
            result["canonical_actual_supported"] = True
            result["canonical_match"] = bool(receipt["canonical_match"])
            result["mismatch_category"] = receipt["mismatch_category"]
            result["mismatch_path"] = receipt["mismatch_path"]
            result["actual_node_counts"] = _node_counts(actual)
            return result
        finally:
            context.close()


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
