#!/usr/bin/env python3
"""Select note's proven draft filter and observe only safe aggregate list shape.

Recovery-only probe. It performs exactly two UI navigation clicks:
1) open the unique visible publication-status control;
2) select the uniquely proven ``menuitemradio`` named ``下書き``.
It never opens an article/editor and never writes note content, Notion, ledger, or model state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run_p0b_hosted_private_draft_shape_probe as shape
import run_p0b_hosted_private_draft_filter_menu_probe as menu

ARTICLE_LIST_URL = shape.ARTICLE_LIST_URL
RESULT_ENV = "P0B_HOSTED_DRAFT_FILTER_NAV_RESULT_FILE"
SAFE_RESULT_KEYS = {
    "status",
    "authenticated",
    "status_filter_control_count",
    "draft_filter_selected",
    "draft_filter_role",
    "final_route_shape",
    "visible_anchor_count",
    "anchor_route_shape_counts",
    "draft_marker_count",
    "published_marker_count",
    "ui_navigation_click_count",
    "zero_model_calls",
    "mutation_count",
}


def _select_unique_draft_filter(page: Any) -> str:
    """Select only the exact semantic shape already proven by the read-only menu probe."""
    role_counts = menu._visible_exact_actionable_role_counts(page, "下書き")
    expected = {
        "button": 0,
        "link": 0,
        "menuitem": 0,
        "menuitemradio": 1,
        "option": 0,
        "radio": 0,
    }
    if role_counts != expected:
        raise base.NoteDraftError("Draft filter actionable-role shape is not uniquely proven")

    candidate = page.get_by_role("menuitemradio", name="下書き", exact=True)
    try:
        count = int(candidate.count())
    except Exception as exc:
        raise base.NoteDraftError("Could not enumerate the exact draft filter") from exc
    if count != 1:
        raise base.NoteDraftError("Exact draft filter is not uniquely identified")
    try:
        visible = bool(candidate.is_visible(timeout=1000))
    except Exception as exc:
        raise base.NoteDraftError("Could not verify draft filter visibility") from exc
    if not visible:
        raise base.NoteDraftError("Exact draft filter is not visible")
    candidate.click()
    page.wait_for_timeout(1500)
    return "menuitemradio"


def probe() -> dict[str, Any]:
    """Navigate to the draft-filtered list and return only aggregate, redacted facts."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for the hosted draft-filter navigation probe") from exc

    storage_state = shape._storage_state()
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

                status_filter_control_count = menu._open_status_filter_menu(page)
                draft_filter_role = _select_unique_draft_filter(page)
                if base._looks_logged_out(page):
                    raise base.NoteAuthenticationExpired("Hosted draft-filtered session is not authenticated")

                visible_anchor_count, route_counts = shape._visible_route_shapes(page)
                body_text = str(page.locator("body").inner_text(timeout=10000) or "")
                result = {
                    "status": "draft_filter_selected_no_content_mutation",
                    "authenticated": True,
                    "status_filter_control_count": status_filter_control_count,
                    "draft_filter_selected": True,
                    "draft_filter_role": draft_filter_role,
                    "final_route_shape": shape._safe_route_shape(str(page.url or "")),
                    "visible_anchor_count": visible_anchor_count,
                    "anchor_route_shape_counts": route_counts,
                    "draft_marker_count": body_text.count("下書き"),
                    "published_marker_count": body_text.count("公開"),
                    "ui_navigation_click_count": 2,
                    "zero_model_calls": True,
                    "mutation_count": 0,
                }
                if set(result) != SAFE_RESULT_KEYS:
                    raise base.NoteDraftError("Hosted draft-filter navigation result schema drifted")
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
    print("P0B_HOSTED_PRIVATE_DRAFT_FILTER_NAV_PROBE=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
