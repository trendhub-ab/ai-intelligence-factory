#!/usr/bin/env python3
"""Run298 final in-place refresh for the exact existing Netflix GenRec draft.

This entrypoint keeps the exact existing-route/title/single-match guards. For an existing
header it uses only the proven large header image, reveals its upper-right hover control,
requires one geometrically isolated safe control, removes the old header, verifies that
note exposes the normal add-image UI, uploads the reviewed eyecatch through the existing
official UI path, and proves the header media changed. Only after that succeeds is the
canonical current manuscript written to the same draft.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import note_draft_automation as note_base
import note_eyecatch_persistence as persistence
import run190_note_persistent_cloud as cloud
import run193_note_official_header_upload as official_header
import run295_note_private_draft_audit as audit295
import run292_note_rendered_body_audit as audit292
import run291_note_private_draft_audit as audit_base
import run296_editorial_format_v2 as r296
import run298_genrec_inplace_refresh as base


_REJECT = (
    "公開", "投稿", "下書き", "保存", "キャンセル", "戻る", "メニュー",
    "post", "save", "cancel", "back", "menu",
)
_STRONG = ("削除", "閉じる", "remove", "close", "見出し", "画像", "×")


class Run298HoverHeaderError(RuntimeError):
    pass


def _semantic(control: Any) -> str:
    parts: list[str] = []
    for getter in (
        lambda: control.get_attribute("aria-label"),
        lambda: control.get_attribute("title"),
        lambda: control.get_attribute("data-testid"),
        lambda: control.inner_text(timeout=180),
    ):
        try:
            value = getter()
        except Exception:
            value = None
        if value:
            parts.append(str(value).strip())
    return " ".join(parts).strip().lower()[:240]


def _one_header_image(page: Any, title_field: Any) -> tuple[Any, dict[str, float]]:
    try:
        title_box = title_field.bounding_box() or {}
        title_y = float(title_box.get("y", -1))
    except Exception:
        title_y = -1
    images = page.locator("img")
    matches: list[tuple[int, Any, dict[str, float]]] = []
    try:
        count = min(images.count(), 80)
    except Exception:
        count = 0
    for index in range(count):
        item = images.nth(index)
        try:
            if not item.is_visible(timeout=120):
                continue
            box = item.bounding_box()
            if not box:
                continue
            width = float(box.get("width", 0)); height = float(box.get("height", 0)); top = float(box.get("y", 999999))
            natural = item.evaluate("el => [Number(el.naturalWidth || 0), Number(el.naturalHeight || 0)]")
            natural_w = float(natural[0]); natural_h = float(natural[1])
        except Exception:
            continue
        top_limit = title_y + 160 if title_y >= 0 else 760
        if width >= 420 and height >= 140 and top < top_limit and top > -500 and natural_w >= 600 and natural_h >= 200:
            matches.append((index, item, {"x": float(box["x"]), "y": top, "width": width, "height": height}))
    if len(matches) != 1:
        raise Run298HoverHeaderError(f"header_image_not_unique:{len(matches)}")
    return matches[0][1], matches[0][2]


def _hover_remove_control(page: Any, header: Any, box: dict[str, float]) -> tuple[Any, int, bool]:
    try:
        header.hover(timeout=3000)
        page.mouse.move(box["x"] + box["width"] - 18, box["y"] + 18)
        page.wait_for_timeout(650)
    except Exception as exc:
        raise Run298HoverHeaderError("header_hover_failed") from exc

    controls = page.locator('button, [role="button"], [aria-label], [title]')
    candidates: list[tuple[int, Any, str]] = []
    try:
        count = min(controls.count(), 180)
    except Exception:
        count = 0
    right = box["x"] + box["width"]
    top = box["y"]
    for index in range(count):
        control = controls.nth(index)
        try:
            if not control.is_visible(timeout=100):
                continue
            cbox = control.bounding_box()
            if not cbox:
                continue
            width = float(cbox.get("width", 0)); height = float(cbox.get("height", 0))
            cx = float(cbox.get("x", 0)) + width / 2.0
            cy = float(cbox.get("y", 0)) + height / 2.0
        except Exception:
            continue
        if width < 12 or width > 76 or height < 12 or height > 76:
            continue
        if cx < right - 115 or cx > right + 34 or cy < top - 38 or cy > top + 105:
            continue
        semantic = _semantic(control)
        if any(term in semantic for term in _REJECT):
            continue
        candidates.append((index, control, semantic))

    strong = [row for row in candidates if any(term in row[2] for term in _STRONG)]
    selected: list[tuple[int, Any, str]]
    strong_semantic = False
    if len(strong) == 1:
        selected = strong
        strong_semantic = True
    elif len(strong) > 1:
        raise Run298HoverHeaderError(f"header_hover_control_ambiguous_strong:{len(strong)}")
    else:
        selected = candidates
    if len(selected) != 1:
        raise Run298HoverHeaderError(f"header_hover_control_not_unique:{len(selected)}")
    return selected[0][1], len(candidates), strong_semantic


def _wait_for_add_control(page: Any, seconds: float = 8.0) -> Any:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            control = official_header._find_header_add_control(page)
            if control is not None:
                return control
        except Exception:
            pass
        page.wait_for_timeout(300)
    raise Run298HoverHeaderError("header_add_control_not_exposed_after_remove")


def _replace_existing_header(page: Any, image_path: Path, title_field: Any) -> dict[str, Any]:
    metrics = persistence.collect_eyecatch_metrics(page, title_locator=title_field)
    if not persistence.eyecatch_persistence_confirmed(metrics):
        raise Run298HoverHeaderError("existing_header_not_proven")
    before_hash, before_count = base._header_media_fingerprint(page, title_field)
    if not before_hash or before_count != 1:
        raise Run298HoverHeaderError(f"existing_header_fingerprint_not_exact:{before_count}")

    header, box = _one_header_image(page, title_field)
    control, hover_candidate_count, strong_semantic = _hover_remove_control(page, header, box)
    try:
        control.click()
    except Exception as exc:
        raise Run298HoverHeaderError("header_remove_control_click_failed") from exc
    page.wait_for_timeout(650)

    _wait_for_add_control(page)
    after_remove_hash, after_remove_count = base._header_media_fingerprint(page, title_field)
    if after_remove_hash == before_hash and after_remove_count >= 1:
        raise Run298HoverHeaderError("existing_header_still_present_after_remove")

    official_header._upload_header_image(page, image_path)
    page.wait_for_timeout(850)
    title_field = note_base._find_title(page)
    after_hash, after_count = base._header_media_fingerprint(page, title_field)
    final_metrics = persistence.collect_eyecatch_metrics(page, title_locator=title_field)
    if not persistence.eyecatch_persistence_confirmed(final_metrics):
        raise Run298HoverHeaderError("replacement_header_not_proven")
    if not after_hash or after_count < 1 or after_hash == before_hash:
        raise Run298HoverHeaderError("replacement_header_fingerprint_not_changed")
    return {
        "before_header_media_hash": before_hash,
        "after_header_media_hash": after_hash,
        "header_media_changed": True,
        "hover_candidate_count": hover_candidate_count,
        "hover_control_strong_semantic": strong_semantic,
    }


def _renderer_faithful_audit(page: Any, title: str, manuscript: str) -> dict[str, Any]:
    original_metric = audit_base._body_text_metrics
    try:
        audit_base._body_text_metrics = audit292._body_text_metrics
        wrapped = audit295._audit_wrapper(audit_base._audit_current_page)
        return wrapped(page, title, manuscript)
    except Exception as exc:
        raise Run298HoverHeaderError(f"post_update_audit_failed:{type(exc).__name__}") from exc
    finally:
        audit_base._body_text_metrics = original_metric


def refresh() -> dict[str, Any]:
    base._ensure_private_queue_state()
    article, eyecatch_url = base._expected_current_article()
    title = str(article["title"])
    manuscript = str(article["manuscript"])
    if len(manuscript) < 200:
        raise Run298HoverHeaderError("prepared_manuscript_too_short")

    official_header.install()
    persistence.install_creation_persistence_guard(note_base)
    image_path = note_base._download_eyecatch(eyecatch_url, base.TARGET_SYNC_ID)
    if image_path.stat().st_size < 10_000:
        raise Run298HoverHeaderError("reviewed_eyecatch_download_too_small")
    image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run298HoverHeaderError("playwright_missing") from exc

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
                    raise Run298HoverHeaderError("note_auth_inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
            if base._route_key(str(page.url or "")) != route_key:
                raise Run298HoverHeaderError("existing_editor_route_changed")
            if base._safe_title(page) != title.strip():
                raise Run298HoverHeaderError("existing_draft_title_mismatch")

            title_field = note_base._find_title(page)
            body, before_text = base._visible_body(page, title_field)
            prior_surface = base._require_old_or_current_surface(before_text)

            # Header replacement is deliberately completed before manuscript mutation.
            header_result = _replace_existing_header(page, image_path, title_field)

            title_field = note_base._find_title(page)
            body = note_base._find_body(page, title_field)
            note_base._paste_manuscript(page, body, manuscript)
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, manuscript)

            saved_url = note_base._save_draft_and_verify(page, title, manuscript, image_required=True)
            if base._route_key(saved_url) != route_key or base._route_key(str(page.url or "")) != route_key:
                raise Run298HoverHeaderError("in_place_route_identity_lost")

            page.wait_for_timeout(900)
            audit_metrics = _renderer_faithful_audit(page, title, manuscript)
            title_field = note_base._find_title(page)
            _, after_text = base._visible_body(page, title_field)
            markers = base._new_surface_markers(after_text, title)
            required_markers = [
                "new_intro_present", "old_intro_absent", "what_row_absent",
                "new_cta_heading_present", "new_cta_body_present", "cta_link_label_present",
                "sources_before_cta",
            ]
            if not all(markers[key] for key in required_markers) or markers["duplicate_title_prefix"]:
                raise Run298HoverHeaderError("post_update_run296_markers_failed")

            final_hash, final_count = base._header_media_fingerprint(page, title_field)
            if final_hash != header_result["after_header_media_hash"] or final_count < 1:
                raise Run298HoverHeaderError("replacement_header_not_persistent")
            base._ensure_private_queue_state()

            return {
                "status": "updated_in_place",
                "sync_id": base.TARGET_SYNC_ID,
                "same_private_draft_route": True,
                "editor_route_hash": route_hash,
                "history_candidate_count": candidate_count,
                "matched_history_rank": matched_rank,
                "prior_surface": prior_surface,
                "title_match": bool(audit_metrics.get("title_match")),
                **markers,
                "body_h1_count": int(audit_metrics.get("body_h1_count", -1)),
                "heading_count": int(audit_metrics.get("heading_count", -1)),
                "eyecatch_present": bool(audit_metrics.get("eyecatch_present")),
                "eyecatch_proof_mode": str(audit_metrics.get("eyecatch_proof_mode") or ""),
                **header_result,
                "run296_eyecatch_sha256": image_sha,
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
    result = refresh()
    _write_result(os.environ.get("RUN298_RESULT_FILE", ""), result)
    print(json.dumps({
        "status": result["status"],
        "same_private_draft_route": result["same_private_draft_route"],
        "header_media_changed": result["header_media_changed"],
        "quality_state_ready": result["quality_state_ready"],
        "posting_state_preparing": result["posting_state_preparing"],
        "public_release": result["public_release"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
