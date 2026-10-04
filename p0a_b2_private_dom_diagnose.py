#!/usr/bin/env python3
"""Read-only structural diagnosis of the most recent synthetic P0-A/B2 private proof draft.

No note mutation, no model calls, no Notion access, no screenshots. Private edit URLs, draft
identities, title text and body text never cross the process boundary. Output is limited to
structural counts and categorical canonical mismatch information.
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


def _title_value(field: Any) -> str:
    tag = str(field.evaluate("el => el.tagName.toLowerCase()"))
    if tag in {"input", "textarea"}:
        return str(field.input_value() or "").strip()
    return str(field.inner_text() or "").strip()


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
    manuscript = run222.prepare_note_editor_manuscript(proof.FIXTURE_SOURCE, proof.FIXTURE_TITLE)
    expected = contract.parse_presentation_markdown(manuscript)
    result: dict[str, object] = {
        "status": "private_dom_diagnostic_complete",
        "read_only": True,
        "zero_gemini_calls": True,
        "notion_access": False,
        "public_release": False,
        "draft_mutation": False,
        "found_matching_private_draft": False,
        "expected_node_counts": _node_counts(expected),
    }

    recent_urls = cloud._recent_private_edit_urls(cloud._profile_dir())
    result["recent_private_edit_route_count"] = len(recent_urls)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            for private_url in recent_urls[:12]:
                try:
                    page.goto(private_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(900)
                    if base._looks_logged_out(page):
                        continue
                    if not run187._is_editor_url(str(page.url or "")):
                        continue
                    title_field = base._find_title(page)
                    if _title_value(title_field) != proof.FIXTURE_TITLE:
                        continue
                    body = base._find_body(page, title_field)
                    snapshot = dom.snapshot_note_body(body)
                    result["found_matching_private_draft"] = True
                    result.update(dom.safe_snapshot_diagnostics(snapshot))
                    try:
                        actual = dom.document_from_note_snapshot(
                            snapshot,
                            allowed_normalizations=(contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,),
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
                except Exception:
                    continue
        finally:
            context.close()
    return result


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
