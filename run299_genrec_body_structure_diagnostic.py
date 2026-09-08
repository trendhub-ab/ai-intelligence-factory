#!/usr/bin/env python3
"""Read-only structural diagnostics for the exact existing Netflix GenRec private draft.

Emits only counts, geometry, and known publication-marker multiplicities. It never emits
unpublished body text, draft/image URLs, DOM HTML, or performs any mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as note_base
import run190_note_persistent_cloud as cloud
import run296_editorial_format_v2 as r296
import run298_genrec_inplace_refresh as base


class Run299DiagnosticError(RuntimeError):
    pass


def _counts(text: str) -> dict[str, int]:
    value = str(text or "")
    return {
        "new_intro_count": value.count(r296.INTRO_HEADING_NEW),
        "old_intro_count": value.count(r296.INTRO_HEADING_OLD),
        "removed_summary_label_count": value.count(r296.REMOVE_SUMMARY_LABEL),
        "cta_heading_count": value.count(r296.CTA_HEADING),
        "cta_link_label_count": value.count(r296.CTA_LINK_LABEL),
        "sources_heading_count": value.count("Sources / Evidence"),
    }


def _element_metrics(item: Any, index: int) -> dict[str, Any]:
    try:
        box = item.bounding_box() or {}
    except Exception:
        box = {}
    try:
        text = str(item.inner_text(timeout=2500) or "")
    except Exception:
        text = ""
    try:
        tag = str(item.evaluate("el => el.tagName.toLowerCase()"))
    except Exception:
        tag = ""
    try:
        role = str(item.get_attribute("role") or "")
    except Exception:
        role = ""
    try:
        placeholder = str(item.get_attribute("data-placeholder") or item.get_attribute("aria-label") or "")
    except Exception:
        placeholder = ""
    try:
        descendants = int(item.locator('[contenteditable="true"]').count())
    except Exception:
        descendants = -1
    return {
        "index": index,
        "tag": tag,
        "role": role[:40],
        "has_body_label": bool("本文" in placeholder),
        "x": round(float(box.get("x", -1)), 1),
        "y": round(float(box.get("y", -1)), 1),
        "width": round(float(box.get("width", -1)), 1),
        "height": round(float(box.get("height", -1)), 1),
        "visible_chars": len(text),
        "contenteditable_descendant_count": descendants,
        **_counts(text),
    }


def collect() -> dict[str, Any]:
    base._ensure_private_queue_state()
    article, _ = base._expected_current_article()
    title = str(article.get("title") or "").strip()
    if not title:
        raise Run299DiagnosticError("expected_title_missing")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run299DiagnosticError("playwright_missing") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, rank, candidate_count = base._find_one_existing_route(context, page, title)
            route_key = base._route_key(route)
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
            if note_base._looks_logged_out(page):
                if not cloud._seed_note_state(context, page):
                    raise Run299DiagnosticError("note_auth_inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1200)
            if base._route_key(str(page.url or "")) != route_key:
                raise Run299DiagnosticError("editor_route_changed")
            if base._safe_title(page) != title:
                raise Run299DiagnosticError("title_mismatch")

            title_field = note_base._find_title(page)
            selected = note_base._find_body(page, title_field)
            selected_metrics = _element_metrics(selected, -1)

            locator = page.locator('[contenteditable="true"]')
            visible: list[dict[str, Any]] = []
            try:
                total = min(locator.count(), 24)
            except Exception:
                total = 0
            for index in range(total):
                item = locator.nth(index)
                try:
                    if not item.is_visible(timeout=150):
                        continue
                except Exception:
                    continue
                visible.append(_element_metrics(item, index))

            return {
                "status": "diagnostic_complete",
                "read_only": True,
                "draft_mutation": False,
                "public_release": False,
                "zero_gemini_calls": True,
                "same_private_draft_route": True,
                "editor_route_hash": hashlib.sha256(route_key.encode("utf-8")).hexdigest()[:12],
                "history_candidate_count": candidate_count,
                "matched_history_rank": rank,
                "visible_contenteditable_count": len(visible),
                "selected_body": selected_metrics,
                "visible_contenteditables": visible,
            }
        finally:
            context.close()


def main() -> int:
    result = collect()
    path_value = os.environ.get("RUN299_RESULT_FILE", "")
    if path_value:
        target = Path(path_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
