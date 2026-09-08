#!/usr/bin/env python3
"""Run300: repair the exact duplicated Netflix GenRec private draft body in place.

The header was already replacement-proven and saved by Run298, so Run300 never touches it.
Run299 proved one visible body contenteditable containing one legacy and one current surface.
This repair selects exactly that editor's contents with the DOM Selection API, verifies the
selection is fully contained and covers the body, deletes through the editor keyboard path,
requires the body to become empty, pastes the canonical current manuscript once, saves the
same /edit route, and performs a renderer-faithful final audit.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image

import note_draft_automation as note_base
import note_eyecatch_persistence as persistence
import run190_note_persistent_cloud as cloud
import run292_note_rendered_body_audit as audit292
import run295_note_private_draft_audit as audit295
import run291_note_private_draft_audit as audit_base
import run296_editorial_format_v2 as r296
import run298_genrec_inplace_refresh as base


class Run300Error(RuntimeError):
    pass


def _normalized(value: str) -> str:
    return audit_base._normalized_visible(str(value or ""))


def _marker_counts(text: str) -> dict[str, int]:
    value = _normalized(text)
    return {
        "new_intro_count": value.count(r296.INTRO_HEADING_NEW),
        "old_intro_count": value.count(r296.INTRO_HEADING_OLD),
        "removed_summary_label_count": value.count(r296.REMOVE_SUMMARY_LABEL),
        "cta_heading_count": value.count(r296.CTA_HEADING),
        "cta_link_label_count": value.count(r296.CTA_LINK_LABEL),
        "sources_heading_count": value.count("Sources / Evidence"),
    }


def _classify_current_body(text: str) -> str:
    counts = _marker_counts(text)
    duplicated = {
        "new_intro_count": 1,
        "old_intro_count": 1,
        "removed_summary_label_count": 1,
        "cta_heading_count": 1,
        "cta_link_label_count": 1,
        "sources_heading_count": 2,
    }
    canonical = {
        "new_intro_count": 1,
        "old_intro_count": 0,
        "removed_summary_label_count": 0,
        "cta_heading_count": 1,
        "cta_link_label_count": 1,
        "sources_heading_count": 1,
    }
    if counts == duplicated:
        return "run298_duplicate"
    if counts == canonical:
        return "canonical"
    raise Run300Error("body_surface_not_exact_repair_target")


def _selection_metrics(body: Any) -> dict[str, Any]:
    try:
        raw = body.evaluate(
            """el => {
                const sel = window.getSelection();
                if (!sel || sel.rangeCount !== 1) return {inside:false, selected:0, body:0};
                const compact = s => String(s || '').replace(/[\s\u200b\u2060]+/g, '');
                const anchorInside = !!sel.anchorNode && (sel.anchorNode === el || el.contains(sel.anchorNode));
                const focusInside = !!sel.focusNode && (sel.focusNode === el || el.contains(sel.focusNode));
                return {
                    inside: anchorInside && focusInside,
                    selected: compact(sel.toString()).length,
                    body: compact(el.innerText || '').length,
                };
            }"""
        )
    except Exception as exc:
        raise Run300Error("body_selection_metrics_failed") from exc
    return {
        "inside": bool((raw or {}).get("inside")),
        "selected": int((raw or {}).get("selected", 0) or 0),
        "body": int((raw or {}).get("body", 0) or 0),
    }


def _select_exact_body_contents(body: Any) -> dict[str, Any]:
    try:
        body.focus()
        body.evaluate(
            """el => {
                const sel = window.getSelection();
                if (!sel) throw new Error('selection unavailable');
                const range = document.createRange();
                range.selectNodeContents(el);
                sel.removeAllRanges();
                sel.addRange(range);
            }"""
        )
    except Exception as exc:
        raise Run300Error("exact_body_selection_failed") from exc
    metrics = _selection_metrics(body)
    if not metrics["inside"] or metrics["body"] < 100:
        raise Run300Error("exact_body_selection_not_contained")
    coverage = metrics["selected"] / max(1, metrics["body"])
    if coverage < 0.985 or coverage > 1.015:
        raise Run300Error("exact_body_selection_incomplete")
    metrics["coverage"] = round(coverage, 4)
    return metrics


def _strict_clear_body(page: Any, body: Any) -> dict[str, Any]:
    before = _normalized(str(body.inner_text(timeout=5000) or ""))
    if len(before) < 200:
        raise Run300Error("repair_body_unexpectedly_short")
    selection = _select_exact_body_contents(body)
    try:
        page.keyboard.press("Backspace")
        page.wait_for_timeout(700)
    except Exception as exc:
        raise Run300Error("body_delete_keyboard_failed") from exc

    title_field = note_base._find_title(page)
    cleared = note_base._find_body(page, title_field)
    try:
        after = str(cleared.inner_text(timeout=5000) or "")
    except Exception as exc:
        raise Run300Error("cleared_body_read_failed") from exc
    compact_after = re.sub(r"[\s\u200b\u2060]+", "", after)
    if compact_after:
        raise Run300Error("body_not_empty_after_exact_delete")
    return {
        "selected_body_chars_before_delete": selection["body"],
        "selected_body_chars_for_delete": selection["selected"],
        "selection_coverage": selection["coverage"],
    }


def _paste_canonical_once(page: Any, manuscript: str, title: str) -> dict[str, Any]:
    title_field = note_base._find_title(page)
    body = note_base._find_body(page, title_field)
    safe_html = note_base._markdown_to_safe_html(manuscript)
    try:
        body.focus()
        body.evaluate(
            """(el, payload) => {
                el.focus();
                const data = new DataTransfer();
                data.setData('text/html', payload.html);
                data.setData('text/plain', payload.text);
                const event = new ClipboardEvent('paste', {
                    bubbles: true, cancelable: true, clipboardData: data
                });
                el.dispatchEvent(event);
            }""",
            {"html": safe_html, "text": manuscript},
        )
        page.wait_for_timeout(1400)
    except Exception as exc:
        raise Run300Error("canonical_body_paste_failed") from exc

    title_field = note_base._find_title(page)
    body = note_base._find_body(page, title_field)
    try:
        actual = str(body.inner_text(timeout=5000) or "")
    except Exception as exc:
        raise Run300Error("canonical_body_read_failed") from exc
    counts = _marker_counts(actual)
    if _classify_current_body(actual) != "canonical":
        raise Run300Error("canonical_body_marker_multiplicity_failed")
    try:
        metrics = audit292._body_text_metrics(actual, manuscript, title)
    except Exception as exc:
        raise Run300Error(f"canonical_body_renderer_check_failed:{type(exc).__name__}") from exc
    if float(metrics.get("visible_length_ratio", 0.0)) > 1.15:
        raise Run300Error("canonical_body_visible_ratio_too_large")
    return {**counts, "pre_save_visible_length_ratio": float(metrics.get("visible_length_ratio", 0.0))}


def _renderer_faithful_audit(page: Any, title: str, manuscript: str) -> dict[str, Any]:
    original_metric = audit_base._body_text_metrics
    try:
        audit_base._body_text_metrics = audit292._body_text_metrics
        wrapped = audit295._audit_wrapper(audit_base._audit_current_page)
        return wrapped(page, title, manuscript)
    except Exception as exc:
        raise Run300Error(f"post_save_actual_note_audit_failed:{type(exc).__name__}") from exc
    finally:
        audit_base._body_text_metrics = original_metric


def _require_1280x670_source(eyecatch_url: str) -> tuple[Path, str]:
    image_path = note_base._download_eyecatch(eyecatch_url, base.TARGET_SYNC_ID)
    if image_path.stat().st_size < 10_000:
        raise Run300Error("source_eyecatch_too_small")
    try:
        with Image.open(image_path) as image:
            size = tuple(image.size)
            image.verify()
    except Exception as exc:
        raise Run300Error("source_eyecatch_invalid") from exc
    if size != (1280, 670):
        raise Run300Error(f"source_eyecatch_wrong_dimensions:{size[0]}x{size[1]}")
    return image_path, hashlib.sha256(image_path.read_bytes()).hexdigest()


def repair_and_audit() -> dict[str, Any]:
    base._ensure_private_queue_state()
    article, eyecatch_url = base._expected_current_article()
    title = str(article["title"])
    manuscript = str(article["manuscript"])
    if len(manuscript) < 200:
        raise Run300Error("prepared_manuscript_too_short")

    _image_path, image_sha = _require_1280x670_source(eyecatch_url)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run300Error("playwright_missing") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, matched_rank, candidate_count = base._find_one_existing_route(context, page, title)
            route_key = base._route_key(route)
            route_hash = hashlib.sha256(route_key.encode("utf-8")).hexdigest()[:12]
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
            if note_base._looks_logged_out(page):
                if not cloud._seed_note_state(context, page):
                    raise Run300Error("note_auth_inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1200)
            if base._route_key(str(page.url or "")) != route_key:
                raise Run300Error("existing_editor_route_changed")
            if base._safe_title(page) != title.strip():
                raise Run300Error("existing_draft_title_mismatch")

            title_field = note_base._find_title(page)
            body, before_text = base._visible_body(page, title_field)
            initial_state = _classify_current_body(before_text)

            header_metrics_before = persistence.collect_eyecatch_metrics(page, title_locator=title_field)
            if not persistence.eyecatch_persistence_confirmed(header_metrics_before):
                raise Run300Error("replacement_header_persistence_not_confirmed_before_repair")
            header_hash_before, header_count_before = base._header_media_fingerprint(page, title_field)
            if not header_hash_before or header_count_before < 1:
                raise Run300Error("replacement_header_fingerprint_missing_before_repair")

            clear_metrics: dict[str, Any] = {}
            paste_metrics: dict[str, Any] = {}
            if initial_state == "run298_duplicate":
                clear_metrics = _strict_clear_body(page, body)
                paste_metrics = _paste_canonical_once(page, manuscript, title)
                saved_url = note_base._save_draft_and_verify(page, title, manuscript, image_required=True)
                if base._route_key(saved_url) != route_key or base._route_key(str(page.url or "")) != route_key:
                    raise Run300Error("in_place_route_identity_lost")
                page.wait_for_timeout(1000)
            elif initial_state == "canonical":
                saved_url = str(page.url or "")
            else:
                raise Run300Error("unsupported_initial_body_state")

            audit_metrics = _renderer_faithful_audit(page, title, manuscript)
            title_field = note_base._find_title(page)
            _, final_text = base._visible_body(page, title_field)
            if _classify_current_body(final_text) != "canonical":
                raise Run300Error("final_body_not_canonical")
            markers = base._new_surface_markers(final_text, title)
            required = [
                "new_intro_present", "old_intro_absent", "what_row_absent",
                "new_cta_heading_present", "new_cta_body_present", "cta_link_label_present",
                "sources_before_cta",
            ]
            if not all(markers[key] for key in required) or markers["duplicate_title_prefix"]:
                raise Run300Error("final_publication_markers_failed")
            final_counts = _marker_counts(final_text)
            if final_counts["sources_heading_count"] != 1:
                raise Run300Error("final_sources_multiplicity_failed")

            final_title_field = note_base._find_title(page)
            header_metrics_after = persistence.collect_eyecatch_metrics(page, title_locator=final_title_field)
            if not persistence.eyecatch_persistence_confirmed(header_metrics_after):
                raise Run300Error("replacement_header_persistence_lost")
            header_hash_after, header_count_after = base._header_media_fingerprint(page, final_title_field)
            if not header_hash_after or header_count_after < 1:
                raise Run300Error("replacement_header_fingerprint_missing_after_repair")
            if header_hash_after != header_hash_before:
                raise Run300Error("header_changed_during_body_only_repair")

            base._ensure_private_queue_state()
            return {
                "status": "final_audit_passed",
                "sync_id": base.TARGET_SYNC_ID,
                "same_private_draft_route": True,
                "editor_route_hash": route_hash,
                "history_candidate_count": candidate_count,
                "matched_history_rank": matched_rank,
                "initial_body_state": initial_state,
                "source_eyecatch_width": 1280,
                "source_eyecatch_height": 670,
                "source_eyecatch_sha256": image_sha,
                "header_untouched_during_run300": True,
                "header_persistent": True,
                "title_match": bool(audit_metrics.get("title_match")),
                **markers,
                **final_counts,
                "body_h1_count": int(audit_metrics.get("body_h1_count", -1)),
                "heading_count": int(audit_metrics.get("heading_count", -1)),
                "eyecatch_present": bool(audit_metrics.get("eyecatch_present")),
                "eyecatch_proof_mode": str(audit_metrics.get("eyecatch_proof_mode") or ""),
                "visible_length_ratio": float(audit_metrics.get("visible_length_ratio", 0.0)),
                **clear_metrics,
                **paste_metrics,
                "quality_state_ready": True,
                "posting_state_preparing": True,
                "zero_gemini_calls": True,
                "duplicate_draft_created": False,
                "public_release": False,
                "daily_restarted": False,
            }
        finally:
            context.close()


def _write_result(path_value: str, result: dict[str, Any]) -> None:
    if not path_value:
        return
    target = Path(path_value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    result = repair_and_audit()
    _write_result(os.environ.get("RUN300_RESULT_FILE", ""), result)
    print(json.dumps({
        "status": result["status"],
        "same_private_draft_route": result["same_private_draft_route"],
        "source_eyecatch_dimensions": "1280x670",
        "header_untouched_during_run300": result["header_untouched_during_run300"],
        "public_release": result["public_release"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
