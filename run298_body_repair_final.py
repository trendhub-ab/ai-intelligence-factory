#!/usr/bin/env python3
"""Run298 final body repair for the exact existing Netflix GenRec private draft.

The preceding hover-header run already completed and persisted the reviewed header image, then
exposed a real defect in the legacy in-place body replacement: Ctrl+A did not reliably select
all content in note's current contenteditable, so the canonical manuscript was appended to the
old body. This repair does not touch the header. It requires the existing header to be present,
selects the exact body DOM contents with a Range, deletes that selected content through the
normal keyboard path, proves the editor is empty, pastes the canonical manuscript, verifies a
single rendered body before save, reopens the same route, and performs the strict final audit.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as note_base
import note_eyecatch_persistence as persistence
import run190_note_persistent_cloud as cloud
import run291_note_private_draft_audit as audit_base
import run292_note_rendered_body_audit as audit292
import run295_note_private_draft_audit as audit295
import run298_genrec_inplace_refresh as base


class Run298BodyRepairError(RuntimeError):
    pass


def _normalized_body_text(body: Any) -> str:
    try:
        raw = str(body.inner_text(timeout=5000) or "")
    except Exception as exc:
        raise Run298BodyRepairError("body_read_failed") from exc
    return audit_base._normalized_visible(raw)


def _clear_exact_body(page: Any, body: Any) -> int:
    """Select only the exact contenteditable contents, delete them, and prove they are gone."""
    try:
        body.focus()
        selected = bool(body.evaluate(
            """el => {
                const range = document.createRange();
                range.selectNodeContents(el);
                const selection = window.getSelection();
                if (!selection) return false;
                selection.removeAllRanges();
                selection.addRange(range);
                return selection.rangeCount === 1 && !selection.getRangeAt(0).collapsed;
            }"""
        ))
    except Exception as exc:
        raise Run298BodyRepairError("body_range_selection_failed") from exc
    if not selected:
        raise Run298BodyRepairError("body_range_selection_not_established")
    try:
        page.keyboard.press("Backspace")
        page.wait_for_timeout(650)
    except Exception as exc:
        raise Run298BodyRepairError("body_delete_key_failed") from exc

    remaining = _normalized_body_text(body)
    remaining_chars = len(remaining)
    if remaining_chars > 24:
        raise Run298BodyRepairError(f"body_not_cleared:{remaining_chars}")
    return remaining_chars


def _paste_after_proven_clear(page: Any, body: Any, manuscript: str, title: str) -> dict[str, Any]:
    remaining_chars = _clear_exact_body(page, body)
    safe_html = note_base._markdown_to_safe_html(manuscript)
    try:
        body.focus()
        body.evaluate(
            """(el, payload) => {
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
        page.wait_for_timeout(1200)
    except Exception as exc:
        raise Run298BodyRepairError("canonical_paste_failed") from exc

    actual = _normalized_body_text(body)
    try:
        metrics = audit292._body_text_metrics(actual, manuscript, title)
    except Exception as exc:
        raise Run298BodyRepairError(f"pre_save_body_audit_failed:{type(exc).__name__}") from exc
    if metrics.get("expected_contained_in_actual") is not True:
        raise Run298BodyRepairError("canonical_body_not_contained_pre_save")
    ratio = float(metrics.get("visible_length_ratio", 0) or 0)
    if ratio > 1.15:
        raise Run298BodyRepairError(f"pre_save_body_still_duplicated:{ratio:.4f}")
    metrics["remaining_chars_after_clear"] = remaining_chars
    return metrics


def _strict_post_save_audit(page: Any, title: str, manuscript: str) -> dict[str, Any]:
    original_metric = audit_base._body_text_metrics
    try:
        audit_base._body_text_metrics = audit292._body_text_metrics
        wrapped = audit295._audit_wrapper(audit_base._audit_current_page)
        return wrapped(page, title, manuscript)
    except Exception as exc:
        raise Run298BodyRepairError(f"post_save_audit_failed:{type(exc).__name__}") from exc
    finally:
        audit_base._body_text_metrics = original_metric


def repair() -> dict[str, Any]:
    base._ensure_private_queue_state()
    article, _ = base._expected_current_article()
    title = str(article["title"])
    manuscript = str(article["manuscript"])
    if len(manuscript) < 200:
        raise Run298BodyRepairError("prepared_manuscript_too_short")

    persistence.install_creation_persistence_guard(note_base)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run298BodyRepairError("playwright_missing") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, matched_rank, candidate_count = base._find_one_existing_route(context, page, title)
            route_key = base._route_key(route)
            route_hash = hashlib.sha256(route_key.encode("utf-8")).hexdigest()[:12]
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            if note_base._looks_logged_out(page):
                if not cloud._seed_note_state(context, page):
                    raise Run298BodyRepairError("note_auth_inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
            if base._route_key(str(page.url or "")) != route_key:
                raise Run298BodyRepairError("existing_editor_route_changed")
            if base._safe_title(page) != title.strip():
                raise Run298BodyRepairError("existing_draft_title_mismatch")

            title_field = note_base._find_title(page)
            header_metrics = persistence.collect_eyecatch_metrics(page, title_locator=title_field)
            if not persistence.eyecatch_persistence_confirmed(header_metrics):
                raise Run298BodyRepairError("reviewed_header_not_persistent_before_body_repair")
            header_hash_before, header_count_before = base._header_media_fingerprint(page, title_field)
            if not header_hash_before or header_count_before < 1:
                raise Run298BodyRepairError("header_fingerprint_missing_before_body_repair")

            body = note_base._find_body(page, title_field)
            before_text = _normalized_body_text(body)
            expected_text = audit292._rendered_visible_text(manuscript)
            duplicate_ratio_before = round(len(before_text) / max(1, len(expected_text)), 4)

            pre_save_metrics = _paste_after_proven_clear(page, body, manuscript, title)

            saved_url = note_base._save_draft_and_verify(page, title, manuscript, image_required=True)
            if base._route_key(saved_url) != route_key or base._route_key(str(page.url or "")) != route_key:
                raise Run298BodyRepairError("in_place_route_identity_lost")

            page.wait_for_timeout(900)
            audit_metrics = _strict_post_save_audit(page, title, manuscript)
            title_field = note_base._find_title(page)
            body = note_base._find_body(page, title_field)
            after_text = _normalized_body_text(body)
            markers = base._new_surface_markers(after_text, title)
            required = [
                "new_intro_present", "old_intro_absent", "what_row_absent",
                "new_cta_heading_present", "new_cta_body_present", "cta_link_label_present",
                "sources_before_cta",
            ]
            if not all(markers[key] for key in required) or markers["duplicate_title_prefix"]:
                raise Run298BodyRepairError("post_repair_run296_markers_failed")

            final_ratio = float(audit_metrics.get("visible_length_ratio", 0) or 0)
            if not 0.82 <= final_ratio <= 1.15:
                raise Run298BodyRepairError(f"post_repair_visible_ratio_invalid:{final_ratio:.4f}")
            if audit_metrics.get("expected_contained_in_actual") is not True:
                raise Run298BodyRepairError("post_repair_expected_body_not_contained")

            header_hash_after, header_count_after = base._header_media_fingerprint(page, title_field)
            final_header_metrics = persistence.collect_eyecatch_metrics(page, title_locator=title_field)
            if not persistence.eyecatch_persistence_confirmed(final_header_metrics):
                raise Run298BodyRepairError("reviewed_header_not_persistent_after_body_repair")
            if not header_hash_after or header_count_after < 1 or header_hash_after != header_hash_before:
                raise Run298BodyRepairError("header_changed_during_body_only_repair")

            base._ensure_private_queue_state()
            return {
                "status": "updated_in_place_final",
                "sync_id": base.TARGET_SYNC_ID,
                "same_private_draft_route": True,
                "editor_route_hash": route_hash,
                "history_candidate_count": candidate_count,
                "matched_history_rank": matched_rank,
                "title_match": bool(audit_metrics.get("title_match")),
                **markers,
                "body_h1_count": int(audit_metrics.get("body_h1_count", -1)),
                "heading_count": int(audit_metrics.get("heading_count", -1)),
                "body_visible_chars": int(audit_metrics.get("body_visible_chars", -1)),
                "expected_visible_chars": int(audit_metrics.get("expected_visible_chars", -1)),
                "visible_length_ratio": final_ratio,
                "expected_contained_in_actual": bool(audit_metrics.get("expected_contained_in_actual")),
                "remaining_chars_after_clear": int(pre_save_metrics.get("remaining_chars_after_clear", -1)),
                "duplicate_ratio_before_repair": duplicate_ratio_before,
                "eyecatch_present": bool(audit_metrics.get("eyecatch_present")),
                "eyecatch_proof_mode": str(audit_metrics.get("eyecatch_proof_mode") or ""),
                "header_persisted_unchanged_during_body_repair": True,
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
    result = repair()
    _write_result(os.environ.get("RUN298_RESULT_FILE", ""), result)
    print(json.dumps({
        "status": result["status"],
        "same_private_draft_route": result["same_private_draft_route"],
        "visible_length_ratio": result["visible_length_ratio"],
        "eyecatch_present": result["eyecatch_present"],
        "quality_state_ready": result["quality_state_ready"],
        "posting_state_preparing": result["posting_state_preparing"],
        "public_release": result["public_release"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
