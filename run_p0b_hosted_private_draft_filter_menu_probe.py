#!/usr/bin/env python3
"""Open note's publication-status menu and observe the draft option without content mutation.

This recovery probe is intentionally narrower than the private-draft census. It performs
exactly one semantic UI click (the unique visible ``公開ステータス`` control), then only
counts the visible exact ``下書き`` option and safe actionable-role aggregates. It never
chooses a filter option, opens an article card, visits the editor, or writes note/Notion/
ledger state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run_p0b_hosted_private_draft_shape_probe as shape

ARTICLE_LIST_URL = shape.ARTICLE_LIST_URL
RESULT_ENV = "P0B_HOSTED_DRAFT_FILTER_MENU_RESULT_FILE"
ACTIONABLE_ROLES = ("button", "link", "menuitem", "menuitemradio", "option", "radio")
SAFE_RESULT_KEYS = {
    "status",
    "authenticated",
    "status_filter_control_count",
    "draft_filter_option_count",
    "draft_actionable_role_counts",
    "final_route_shape",
    "zero_model_calls",
    "mutation_count",
}


def _wait_for_unique_visible_exact_text(page: Any, label: str, attempts=32, interval_ms=250) -> Any:
    """Wait boundedly for exactly one visible exact-text node; fail closed on ambiguity."""
    controls = page.get_by_text(label, exact=True)
    for attempt in range(attempts):
        try:
            count = min(int(controls.count()), 100)
        except Exception as exc:
            raise base.NoteDraftError("Could not enumerate exact article-list controls") from exc
        visible_indices: list[int] = []
        for index in range(count):
            try:
                if controls.nth(index).is_visible(timeout=100):
                    visible_indices.append(index)
            except Exception:
                continue
        if len(visible_indices) > 1:
            raise base.NoteDraftError("Exact article-list control has multiple visible candidates")
        if len(visible_indices) == 1:
            return controls.nth(visible_indices[0])
        if attempt + 1 < attempts:
            page.wait_for_timeout(interval_ms)
    raise base.NoteDraftError("Exact article-list control did not become uniquely visible in time")


def _open_status_filter_menu(page: Any) -> int:
    """Open exactly one visible publication-status control and nothing else."""
    control = _wait_for_unique_visible_exact_text(page, "公開ステータス")
    control.click()
    page.wait_for_timeout(500)
    return 1


def _visible_exact_text_count(page: Any, label: str) -> int:
    return shape._visible_exact_text_count(page, label)


def _visible_exact_actionable_role_counts(page: Any, label: str) -> dict[str, int]:
    """Count visible exact-name actionable candidates by a fixed safe role set."""
    result: dict[str, int] = {}
    for role in ACTIONABLE_ROLES:
        locator = page.get_by_role(role, name=label, exact=True)
        try:
            count = min(int(locator.count()), 100)
        except Exception as exc:
            raise base.NoteDraftError("Could not enumerate exact actionable draft-filter roles") from exc
        visible = 0
        for index in range(count):
            try:
                if locator.nth(index).is_visible(timeout=100):
                    visible += 1
            except Exception:
                continue
        result[role] = visible
    return result


def probe() -> dict[str, Any]:
    """Open the status menu once and return only aggregate, no-content-mutation facts."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for the hosted filter-menu probe") from exc

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

                status_filter_control_count = _open_status_filter_menu(page)
                draft_filter_option_count = _visible_exact_text_count(page, "下書き")
                draft_actionable_role_counts = _visible_exact_actionable_role_counts(page, "下書き")
                result = {
                    "status": "filter_menu_observed_no_content_mutation",
                    "authenticated": True,
                    "status_filter_control_count": status_filter_control_count,
                    "draft_filter_option_count": draft_filter_option_count,
                    "draft_actionable_role_counts": draft_actionable_role_counts,
                    "final_route_shape": shape._safe_route_shape(str(page.url or "")),
                    "zero_model_calls": True,
                    "mutation_count": 0,
                }
                if set(result) != SAFE_RESULT_KEYS:
                    raise base.NoteDraftError("Hosted filter-menu probe result schema drifted")
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
    print("P0B_HOSTED_PRIVATE_DRAFT_FILTER_MENU_PROBE=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
