#!/usr/bin/env python3
"""Run298: read-only diagnostics for the exact existing GenRec note header.

The diagnostic opens only the already-matched private `/edit` route, verifies the exact title,
and emits non-content counts/booleans needed to choose a safe existing-header replacement path.
It does not perform browser mutation, image capture, publication, or expose draft/image URLs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as note_base
import note_eyecatch_persistence as persistence
import run188_note_header_upload_fallback as run188
import run190_note_persistent_cloud as cloud
import run193_note_official_header_upload as run193
import run298_genrec_inplace_refresh as run298


class Run298HeaderDiagnosticError(RuntimeError):
    pass


def _safe_route_hash(value: str) -> str:
    key = run298._route_key(value)
    if not key:
        return ""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _header_clickability_metrics(page: Any, title_field: Any) -> dict[str, int]:
    try:
        box = title_field.bounding_box() or {}
        title_y = float(box.get("y", -1))
    except Exception:
        title_y = -1
    try:
        raw = page.evaluate(
            """(titleY) => {
                const visible = (el) => {
                    const s = getComputedStyle(el), r = el.getBoundingClientRect();
                    return s.display !== 'none' && s.visibility !== 'hidden' &&
                           s.opacity !== '0' && r.width > 1 && r.height > 1;
                };
                const topLimit = titleY >= 0 ? titleY + 160 : Math.min(innerHeight, 760);
                const media = [];
                for (const el of Array.from(document.querySelectorAll('img, picture, figure, div, section'))) {
                    if (!visible(el)) continue;
                    const r = el.getBoundingClientRect();
                    if (!(r.width >= 420 && r.height >= 140 && r.top < topLimit && r.top > -500)) continue;
                    let mediaLike = false;
                    if (el.tagName === 'IMG') {
                        mediaLike = Number(el.naturalWidth || 0) >= 600 && Number(el.naturalHeight || 0) >= 200;
                    } else if (el.tagName === 'PICTURE' || el.tagName === 'FIGURE') {
                        mediaLike = el.querySelector('img') !== null;
                    } else {
                        const bg = getComputedStyle(el).backgroundImage || '';
                        mediaLike = Boolean(bg && bg !== 'none');
                    }
                    if (mediaLike) media.push(el);
                }
                const clickAncestors = new Set();
                const pointerAncestors = new Set();
                for (const el of media) {
                    let cur = el;
                    for (let i = 0; cur && i < 7; i += 1, cur = cur.parentElement) {
                        if (cur.matches && cur.matches('button, [role="button"], a')) clickAncestors.add(cur);
                        if (getComputedStyle(cur).cursor === 'pointer') pointerAncestors.add(cur);
                    }
                }
                return {
                    large_media_candidate_count: media.length,
                    large_media_clickable_ancestor_count: clickAncestors.size,
                    large_media_pointer_ancestor_count: pointerAncestors.size,
                };
            }""",
            title_y,
        )
    except Exception:
        raw = {}
    result: dict[str, int] = {}
    for key in (
        "large_media_candidate_count",
        "large_media_clickable_ancestor_count",
        "large_media_pointer_ancestor_count",
    ):
        try:
            result[key] = int((raw or {}).get(key, 0) or 0)
        except Exception:
            result[key] = 0
    return result


def _official_add_control_available(page: Any) -> bool:
    try:
        return run193._find_header_add_control(page) is not None
    except Exception:
        return False


def collect() -> dict[str, Any]:
    run298._ensure_private_queue_state()
    article, _ = run298._expected_current_article()
    title = str(article.get("title") or "").strip()
    if not title:
        raise Run298HeaderDiagnosticError("expected_title_missing")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run298HeaderDiagnosticError("playwright_missing") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, matched_rank, candidate_count = run298._find_one_existing_route(context, page, title)
            route_key = run298._route_key(route)
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            if note_base._looks_logged_out(page):
                if not cloud._seed_note_state(context, page):
                    raise Run298HeaderDiagnosticError("note_auth_inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
            if run298._route_key(str(page.url or "")) != route_key:
                raise Run298HeaderDiagnosticError("editor_route_changed")
            if run298._safe_title(page) != title:
                raise Run298HeaderDiagnosticError("title_mismatch")

            title_field = note_base._find_title(page)
            proof_metrics = persistence.collect_eyecatch_metrics(page, title_locator=title_field)
            proof_mode = persistence.classify_eyecatch_persistence(proof_metrics)
            safe_input, safe_image_input_count = run188._safe_header_file_input(page)
            fingerprint, fingerprint_count = run298._header_media_fingerprint(page, title_field)

            result: dict[str, Any] = {
                "status": "diagnostic_complete",
                "read_only": True,
                "zero_gemini_calls": True,
                "draft_mutation": False,
                "public_release": False,
                "same_private_draft_route": True,
                "editor_route_hash": _safe_route_hash(route),
                "history_candidate_count": candidate_count,
                "matched_history_rank": matched_rank,
                "eyecatch_proof_mode": proof_mode,
                "eyecatch_persistence_confirmed": persistence.eyecatch_persistence_confirmed(proof_metrics),
                "safe_header_file_input_available": safe_input is not None,
                "safe_image_input_count": int(safe_image_input_count),
                "official_add_control_available": _official_add_control_available(page),
                "header_fingerprint_available": bool(fingerprint and fingerprint_count > 0),
                "header_fingerprint_count": int(fingerprint_count),
            }
            for key, value in proof_metrics.items():
                if isinstance(value, (bool, int, float)):
                    result[key] = value
            result.update(_header_clickability_metrics(page, title_field))
            return result
        finally:
            context.close()


def _write_result(path_value: str, result: dict[str, Any]) -> None:
    if not path_value:
        return
    target = Path(path_value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    result = collect()
    _write_result(os.environ.get("RUN298_HEADER_DIAGNOSTIC_RESULT", ""), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())