#!/usr/bin/env python3
"""Run298: update the one existing Netflix GenRec private note draft in place.

Safety boundary:
- exact fixed sync_id and exact current Run296 source/eyecatch only;
- requires Note Ready = Ready / 投稿準備中 and no public-post evidence;
- discovers only existing /notes/<id>/edit routes from the persistent Chrome History DB;
- requires exactly one matching existing draft and never navigates to /new;
- replaces body + header eyecatch in the same editor route, then reloads and audits it;
- exposes only non-content booleans/counts/hashes;
- ZERO Gemini/model calls and no public-release action.

This module intentionally does not update the Note Ready posting state. The private draft remains
投稿準備中 after the in-place editor save.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as note_base
import note_eyecatch_persistence as eyecatch
import note_ready_sync as ready_sync
import publication_contract as contract
import run190_note_persistent_cloud as cloud
import run193_note_official_header_upload as official_header
import run222_note_presentation_integrity as r222
import run291_note_private_draft_audit as audit_base
import run292_note_rendered_body_audit as audit292
import run295_note_private_draft_audit as audit295
import run296_editorial_format_v2 as r296

TARGET_SYNC_ID = "3bd479ffdca9817f926aeaffbb779c4b"
PREPARING_STATUS = "投稿準備中"


class Run298Error(RuntimeError):
    pass


def _route_key(value: str) -> str:
    parsed = urlparse(str(value or ""))
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"note.com", "editor.note.com"}:
        return ""
    path = (parsed.path or "").rstrip("/")
    if not re.fullmatch(r"/notes/[^/?#]+/edit", path, flags=re.I):
        return ""
    return path.lower()


def _safe_title(page: Any) -> str:
    try:
        return audit_base._title_value(page)
    except Exception as exc:
        raise Run298Error("draft_title_read_failed") from exc


def _expected_current_article() -> tuple[dict[str, Any], str]:
    r222.CTA_HEADINGS.add(r296.CTA_HEADING)
    try:
        article = audit_base._expected_article(TARGET_SYNC_ID)
    except Exception as exc:
        raise Run298Error(f"current_article_guard_failed:{type(exc).__name__}") from exc
    if article.get("sync_id") != TARGET_SYNC_ID:
        raise Run298Error("target_sync_id_drift")
    if not r296.is_genrec_title(str(article.get("title") or "")):
        raise Run298Error("target_title_drift")

    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{TARGET_SYNC_ID}")
    if response.status_code != 200:
        raise Run298Error(f"source_page_read_http_{response.status_code}")
    state = ready_sync._source_state(response.json())
    if not state or state.get("sync_id") != TARGET_SYNC_ID:
        raise Run298Error("source_state_invalid")
    eyecatch_url = str(state.get("eyecatch_url") or "")
    expected_name = f"genrec-run296-{contract.policy_sha256()[:12]}.png"
    parsed = urlparse(eyecatch_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "raw.githubusercontent.com"
        or not parsed.path.endswith(f"/eyecatch_images/{expected_name}")
    ):
        raise Run298Error("source_eyecatch_is_not_run296_version")
    return article, eyecatch_url


def _ensure_private_queue_state() -> None:
    row = audit_base._destination_row(TARGET_SYNC_ID)
    if row.get("sync_id") != TARGET_SYNC_ID:
        raise Run298Error("destination_sync_id_drift")


def _seed_if_needed(context: Any, page: Any, candidate: str, seeded: bool) -> bool:
    if not note_base._looks_logged_out(page):
        return seeded
    if seeded:
        return seeded
    seeded = bool(cloud._seed_note_state(context, page))
    if seeded:
        page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1000)
    return seeded


def _find_one_existing_route(context: Any, page: Any, title: str) -> tuple[str, int, int]:
    candidates = audit_base._recent_private_edit_urls(cloud._profile_dir())
    if not candidates:
        raise Run298Error("no_existing_private_edit_routes")
    matches: list[tuple[str, int]] = []
    seeded = False
    for rank, candidate in enumerate(candidates, start=1):
        if not audit_base._is_note_edit_url(candidate):
            continue
        try:
            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            seeded = _seed_if_needed(context, page, candidate, seeded)
            if note_base._looks_logged_out(page):
                continue
            if not audit_base.run187._is_editor_url(str(page.url or "")):
                continue
            if _safe_title(page) == title.strip():
                matches.append((candidate, rank))
        except Run298Error:
            raise
        except Exception:
            continue
    unique = {}
    for url, rank in matches:
        key = _route_key(url)
        if key:
            unique.setdefault(key, (url, rank))
    if len(unique) != 1:
        raise Run298Error(f"existing_target_draft_not_unique:{len(unique)}")
    url, rank = next(iter(unique.values()))
    return url, rank, len(candidates)


def _visible_body(page: Any, title_field: Any) -> tuple[Any, str]:
    body = note_base._find_body(page, title_field)
    try:
        text = str(body.inner_text(timeout=5000) or "")
    except Exception as exc:
        raise Run298Error("draft_body_read_failed") from exc
    return body, audit_base._normalized_visible(text)


def _header_media_fingerprint(page: Any, title_field: Any) -> tuple[str, int]:
    try:
        box = title_field.bounding_box() or {}
        title_y = float(box.get("y", -1))
    except Exception:
        title_y = -1
    try:
        values = page.evaluate(
            """(titleY) => {
                const visible = (el) => {
                    const s = getComputedStyle(el), r = el.getBoundingClientRect();
                    return s.display !== 'none' && s.visibility !== 'hidden' &&
                           s.opacity !== '0' && r.width > 1 && r.height > 1;
                };
                const topLimit = titleY >= 0 ? titleY + 160 : Math.min(innerHeight, 760);
                const out = [];
                for (const img of Array.from(document.querySelectorAll('img'))) {
                    if (!visible(img)) continue;
                    const r = img.getBoundingClientRect();
                    if (r.width >= 420 && r.height >= 140 && r.top < topLimit && r.top > -500 &&
                        Number(img.naturalWidth || 0) >= 600 && Number(img.naturalHeight || 0) >= 200) {
                        const value = img.currentSrc || img.src || '';
                        if (value) out.push('img:' + value);
                    }
                }
                for (const el of Array.from(document.querySelectorAll('body *'))) {
                    if (!visible(el)) continue;
                    const r = el.getBoundingClientRect();
                    if (!(r.width >= 420 && r.height >= 140 && r.top < topLimit && r.top > -500)) continue;
                    const bg = getComputedStyle(el).backgroundImage || '';
                    if (bg && bg !== 'none') out.push('bg:' + bg);
                }
                return Array.from(new Set(out)).sort();
            }""",
            title_y,
        )
    except Exception:
        values = []
    safe_values = [str(value) for value in (values or []) if value]
    if not safe_values:
        return "", 0
    digest = hashlib.sha256("\n".join(safe_values).encode("utf-8")).hexdigest()[:12]
    return digest, len(safe_values)


def _new_surface_markers(actual: str, title: str) -> dict[str, bool]:
    source_index = actual.find("Sources / Evidence")
    cta_index = actual.find(r296.CTA_HEADING)
    normalized_title = audit_base._normalized_visible(title)
    return {
        "new_intro_present": r296.INTRO_HEADING_NEW in actual,
        "old_intro_absent": r296.INTRO_HEADING_OLD not in actual,
        "what_row_absent": r296.REMOVE_SUMMARY_LABEL not in actual,
        "new_cta_heading_present": r296.CTA_HEADING in actual,
        "new_cta_body_present": audit_base._normalized_visible(r296.CTA_BODY) in actual,
        "cta_link_label_present": r296.CTA_LINK_LABEL in actual,
        "sources_before_cta": source_index >= 0 and cta_index >= 0 and source_index < cta_index,
        "duplicate_title_prefix": bool(normalized_title and actual.startswith(normalized_title)),
    }


def _require_old_or_current_surface(actual: str) -> str:
    markers = _new_surface_markers(actual, r296.GENREC_SOURCE_TITLE)
    if all([
        markers["new_intro_present"],
        markers["old_intro_absent"],
        markers["what_row_absent"],
        markers["new_cta_heading_present"],
        markers["cta_link_label_present"],
    ]):
        return "current"
    if (
        r296.INTRO_HEADING_OLD in actual
        and r296.REMOVE_SUMMARY_LABEL in actual
        and r296.INTRO_HEADING_NEW not in actual
        and r296.CTA_HEADING not in actual
    ):
        return "legacy"
    raise Run298Error("existing_draft_surface_drift")


def _renderer_faithful_audit(page: Any, title: str, manuscript: str) -> dict[str, Any]:
    original_metric = audit_base._body_text_metrics
    try:
        audit_base._body_text_metrics = audit292._body_text_metrics
        wrapped = audit295._audit_wrapper(audit_base._audit_current_page)
        return wrapped(page, title, manuscript)
    except Exception as exc:
        raise Run298Error(f"post_update_audit_failed:{type(exc).__name__}") from exc
    finally:
        audit_base._body_text_metrics = original_metric


def refresh_existing_private_draft() -> dict[str, Any]:
    _ensure_private_queue_state()
    article, eyecatch_url = _expected_current_article()
    title = str(article["title"])
    manuscript = str(article["manuscript"])
    if len(manuscript) < 200:
        raise Run298Error("prepared_manuscript_too_short")

    official_header.install()
    eyecatch.install_creation_persistence_guard(note_base)
    image_path = note_base._download_eyecatch(eyecatch_url, TARGET_SYNC_ID)
    if image_path.stat().st_size < 10_000:
        raise Run298Error("run296_eyecatch_download_too_small")
    image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run298Error("playwright_missing") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, matched_rank, candidate_count = _find_one_existing_route(context, page, title)
            route_key = _route_key(route)
            route_hash = hashlib.sha256(route_key.encode("utf-8")).hexdigest()[:12]
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            if note_base._looks_logged_out(page):
                if not cloud._seed_note_state(context, page):
                    raise Run298Error("note_auth_inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
            if _route_key(str(page.url or "")) != route_key:
                raise Run298Error("existing_editor_route_changed_before_update")
            if _safe_title(page) != title.strip():
                raise Run298Error("existing_draft_title_mismatch")

            title_field = note_base._find_title(page)
            body, before_text = _visible_body(page, title_field)
            prior_surface = _require_old_or_current_surface(before_text)
            before_media_hash, before_media_count = _header_media_fingerprint(page, title_field)

            note_base._paste_manuscript(page, body, manuscript)
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, manuscript)

            note_base._upload_header_image(page, image_path)
            saved_url = note_base._save_draft_and_verify(
                page, title, manuscript, image_required=True
            )
            if _route_key(saved_url) != route_key or _route_key(str(page.url or "")) != route_key:
                raise Run298Error("in_place_route_identity_lost")

            page.wait_for_timeout(900)
            audit_metrics = _renderer_faithful_audit(page, title, manuscript)
            title_field = note_base._find_title(page)
            _, after_text = _visible_body(page, title_field)
            markers = _new_surface_markers(after_text, title)
            if not all([
                markers["new_intro_present"],
                markers["old_intro_absent"],
                markers["what_row_absent"],
                markers["new_cta_heading_present"],
                markers["new_cta_body_present"],
                markers["cta_link_label_present"],
                markers["sources_before_cta"],
                not markers["duplicate_title_prefix"],
            ]):
                raise Run298Error("post_update_run296_markers_failed")

            after_media_hash, after_media_count = _header_media_fingerprint(page, title_field)
            if not after_media_hash or after_media_count < 1:
                raise Run298Error("post_update_header_media_fingerprint_missing")
            if prior_surface == "legacy" and before_media_hash and after_media_hash == before_media_hash:
                raise Run298Error("header_media_did_not_change")

            _ensure_private_queue_state()

            result: dict[str, Any] = {
                "status": "updated_in_place",
                "sync_id": TARGET_SYNC_ID,
                "same_private_draft_route": True,
                "editor_route_hash": route_hash,
                "history_candidate_count": candidate_count,
                "matched_history_rank": matched_rank,
                "prior_surface": prior_surface,
                "title_match": bool(audit_metrics.get("title_match")),
                "new_intro_present": markers["new_intro_present"],
                "old_intro_absent": markers["old_intro_absent"],
                "what_row_absent": markers["what_row_absent"],
                "new_cta_heading_present": markers["new_cta_heading_present"],
                "new_cta_body_present": markers["new_cta_body_present"],
                "cta_link_label_present": markers["cta_link_label_present"],
                "sources_before_cta": markers["sources_before_cta"],
                "duplicate_title_prefix": markers["duplicate_title_prefix"],
                "body_h1_count": int(audit_metrics.get("body_h1_count", -1)),
                "heading_count": int(audit_metrics.get("heading_count", -1)),
                "eyecatch_present": bool(audit_metrics.get("eyecatch_present")),
                "eyecatch_proof_mode": str(audit_metrics.get("eyecatch_proof_mode") or ""),
                "header_media_changed": (
                    bool(before_media_hash)
                    and bool(after_media_hash)
                    and before_media_hash != after_media_hash
                ),
                "before_header_media_hash": before_media_hash,
                "after_header_media_hash": after_media_hash,
                "run296_eyecatch_sha256": image_sha,
                "quality_state_ready": True,
                "posting_state_preparing": True,
                "zero_gemini_calls": True,
                "duplicate_draft_created": False,
                "public_release": False,
                "daily_restarted": False,
            }
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
    result = refresh_existing_private_draft()
    _write_result(os.environ.get("RUN298_RESULT_FILE", ""), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
