#!/usr/bin/env python3
"""Run301: restore the preserved GenRec intro summary in the same private note draft.

Run296 originally removed the ``何が出た？`` label together with its summary body. The corrected
Run296 policy removes only the label. Run301 is a specimen-bound operational repair that:
- requires the corrected current Publication Contract article and exact Netflix GenRec sync_id;
- requires the approved summary exactly once in the current manuscript;
- updates only the one existing private draft route, never creates a new draft;
- preserves the already-approved eyecatch/header byte-for-byte on the note surface;
- uses Run300's exact body selection/clear/paste path to avoid duplicate-body regression;
- performs the renderer-faithful actual-note audit after save;
- makes zero model calls and has no public-release action.
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
import run296_editorial_format_v2 as r296
import run298_genrec_inplace_refresh as base
import run300_genrec_final_body_repair as repair

EXPECTED_SUMMARY = (
    "Netflixがユーザー行動や文脈をテキスト化し、vLLMのprefill-onlyモードでスコアリングを行う"
    "推薦アーキテクチャGenRecを公開した。"
)


class Run301Error(RuntimeError):
    pass


def _normalized(value: str) -> str:
    return audit_base._normalized_visible(str(value or ""))


def _summary_metrics(text: str) -> dict[str, Any]:
    value = _normalized(text)
    summary = _normalized(EXPECTED_SUMMARY)
    intro = _normalized(r296.INTRO_HEADING_NEW)
    why = _normalized("なぜ重要？")
    summary_count = value.count(summary)
    intro_index = value.find(intro)
    summary_index = value.find(summary)
    why_index = value.find(why)
    return {
        "summary_count": summary_count,
        "summary_present_once": summary_count == 1,
        "summary_order_valid": (
            intro_index >= 0
            and summary_index > intro_index
            and why_index > summary_index
        ),
        "what_label_absent": _normalized(r296.REMOVE_SUMMARY_LABEL) not in value,
    }


def _require_corrected_manuscript(manuscript: str) -> dict[str, Any]:
    metrics = _summary_metrics(manuscript)
    if not metrics["summary_present_once"]:
        raise Run301Error("corrected_manuscript_summary_not_exact")
    if not metrics["summary_order_valid"]:
        raise Run301Error("corrected_manuscript_summary_order_invalid")
    if not metrics["what_label_absent"]:
        raise Run301Error("corrected_manuscript_what_label_survived")
    return metrics


def restore_summary_and_audit() -> dict[str, Any]:
    base._ensure_private_queue_state()
    article, eyecatch_url = base._expected_current_article()
    if article.get("sync_id") != base.TARGET_SYNC_ID:
        raise Run301Error("target_sync_id_drift")
    title = str(article["title"])
    manuscript = str(article["manuscript"])
    manuscript_metrics = _require_corrected_manuscript(manuscript)

    _image_path, source_image_sha = repair._require_1280x670_source(eyecatch_url)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run301Error("playwright_missing") from exc

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
                    raise Run301Error("note_auth_inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1200)
            if base._route_key(str(page.url or "")) != route_key:
                raise Run301Error("existing_editor_route_changed")
            if base._safe_title(page) != title.strip():
                raise Run301Error("existing_draft_title_mismatch")

            title_field = note_base._find_title(page)
            body, before_text = base._visible_body(page, title_field)
            if repair._classify_current_body(before_text) != "canonical":
                raise Run301Error("existing_body_not_run300_canonical")
            before_summary = _summary_metrics(before_text)
            if before_summary["summary_count"] not in {0, 1}:
                raise Run301Error("existing_summary_multiplicity_invalid")
            if before_summary["summary_count"] == 1 and not before_summary["summary_order_valid"]:
                raise Run301Error("existing_summary_order_invalid")
            if not before_summary["what_label_absent"]:
                raise Run301Error("existing_what_label_reappeared")

            header_metrics_before = persistence.collect_eyecatch_metrics(page, title_locator=title_field)
            if not persistence.eyecatch_persistence_confirmed(header_metrics_before):
                raise Run301Error("header_persistence_not_confirmed_before_restore")
            header_hash_before, header_count_before = base._header_media_fingerprint(page, title_field)
            if not header_hash_before or header_count_before < 1:
                raise Run301Error("header_fingerprint_missing_before_restore")

            clear_metrics: dict[str, Any] = {}
            paste_metrics: dict[str, Any] = {}
            mutation_performed = before_summary["summary_count"] == 0
            if mutation_performed:
                clear_metrics = repair._strict_clear_body(page, body)
                paste_metrics = repair._paste_canonical_once(page, manuscript, title)
                saved_url = note_base._save_draft_and_verify(
                    page, title, manuscript, image_required=True
                )
                if base._route_key(saved_url) != route_key or base._route_key(str(page.url or "")) != route_key:
                    raise Run301Error("in_place_route_identity_lost")
                page.wait_for_timeout(1000)

            audit_metrics = repair._renderer_faithful_audit(page, title, manuscript)
            title_field = note_base._find_title(page)
            _, final_text = base._visible_body(page, title_field)
            if repair._classify_current_body(final_text) != "canonical":
                raise Run301Error("final_body_not_canonical")
            final_summary = _summary_metrics(final_text)
            if not final_summary["summary_present_once"]:
                raise Run301Error("final_summary_not_exact")
            if not final_summary["summary_order_valid"]:
                raise Run301Error("final_summary_order_invalid")
            if not final_summary["what_label_absent"]:
                raise Run301Error("final_what_label_present")

            markers = base._new_surface_markers(final_text, title)
            required = [
                "new_intro_present", "old_intro_absent", "what_row_absent",
                "new_cta_heading_present", "new_cta_body_present", "cta_link_label_present",
                "sources_before_cta",
            ]
            if not all(markers[key] for key in required) or markers["duplicate_title_prefix"]:
                raise Run301Error("final_publication_markers_failed")
            final_counts = repair._marker_counts(final_text)
            if final_counts["sources_heading_count"] != 1:
                raise Run301Error("final_sources_multiplicity_failed")

            final_title_field = note_base._find_title(page)
            header_metrics_after = persistence.collect_eyecatch_metrics(page, title_locator=final_title_field)
            if not persistence.eyecatch_persistence_confirmed(header_metrics_after):
                raise Run301Error("header_persistence_lost")
            header_hash_after, header_count_after = base._header_media_fingerprint(page, final_title_field)
            if not header_hash_after or header_count_after < 1:
                raise Run301Error("header_fingerprint_missing_after_restore")
            if header_hash_after != header_hash_before:
                raise Run301Error("header_changed_during_body_only_restore")

            base._ensure_private_queue_state()
            return {
                "status": "summary_restored" if mutation_performed else "summary_already_restored",
                "sync_id": base.TARGET_SYNC_ID,
                "same_private_draft_route": True,
                "editor_route_hash": route_hash,
                "history_candidate_count": candidate_count,
                "matched_history_rank": matched_rank,
                "summary_present_before": before_summary["summary_present_once"],
                "summary_present_once": final_summary["summary_present_once"],
                "summary_order_valid": final_summary["summary_order_valid"],
                "what_label_absent": final_summary["what_label_absent"],
                "source_eyecatch_width": 1280,
                "source_eyecatch_height": 670,
                "source_eyecatch_sha256": source_image_sha,
                "header_untouched_during_run301": True,
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
                "manuscript_summary_contract": manuscript_metrics["summary_present_once"],
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
    result = restore_summary_and_audit()
    _write_result(os.environ.get("RUN301_RESULT_FILE", ""), result)
    print(json.dumps({
        "status": result["status"],
        "same_private_draft_route": result["same_private_draft_route"],
        "summary_present_once": result["summary_present_once"],
        "summary_order_valid": result["summary_order_valid"],
        "header_untouched_during_run301": result["header_untouched_during_run301"],
        "public_release": result["public_release"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
