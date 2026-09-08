#!/usr/bin/env python3
"""Run294: diagnose note eyecatch persistence without exposing private draft content.

Run293 identified the existing GenRec private-draft blocker as
``eyecatch_persistence_unconfirmed``. Run294 keeps the exact Run291/292/293
read-only/fail-closed boundary and, only when that fixed guard fires, inspects
non-content DOM structure around the editor header.

It records counts, visibility booleans and geometry-derived media counts only.
It never emits image URLs/src values, unpublished title/body text, the private
draft URL, screenshots, browser storage, or DOM HTML.

ZERO Gemini/model calls. No draft mutation. No public release.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

import run292_note_rendered_body_audit as base292

base = base292.base

EYECATCH_GUARD_MESSAGE = "Private draft eyecatch persistence could not be confirmed"


class Run294EyecatchDiagnosticError(base.PrivateDraftAuditError):
    def __init__(self, code: str, metrics: dict[str, Any]) -> None:
        super().__init__(f"Run294 eyecatch audit failed safely: {code}")
        self.code = str(code)
        self.safe_metrics = dict(metrics)


def _visible_count(locator: Any, *, limit: int = 40) -> tuple[int, int]:
    try:
        total = int(locator.count())
    except Exception:
        return 0, 0
    visible = 0
    for index in range(min(total, limit)):
        try:
            if locator.nth(index).is_visible(timeout=250):
                visible += 1
        except Exception:
            continue
    return total, visible


def _safe_header_media_metrics(page: Any) -> dict[str, Any]:
    """Return only non-content counts/booleans about possible header media."""
    try:
        title_field = base.note_base._find_title(page)
        title_box = base._box(title_field)
    except Exception:
        title_box = None
    title_y = float((title_box or {}).get("y", -1))

    exact = page.locator(
        'button[aria-label="画像を変更"], button[aria-label*="見出し画像を変更"]'
    )
    generic = page.locator(
        'button[aria-label*="画像"], [role="button"][aria-label*="画像"]'
    )
    add_controls = page.locator(
        'button[aria-label="画像を追加"], button[aria-label*="見出し画像"], button:has-text("画像を追加")'
    )
    file_inputs = page.locator('input[type="file"]')

    exact_count, exact_visible = _visible_count(exact)
    generic_count, generic_visible = _visible_count(generic)
    add_count, add_visible = _visible_count(add_controls)
    try:
        file_input_count = int(file_inputs.count())
    except Exception:
        file_input_count = 0

    geometry: dict[str, Any]
    try:
        geometry = page.evaluate(
            """(titleY) => {
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                           style.opacity !== '0' && r.width > 1 && r.height > 1;
                };
                const topLimit = titleY >= 0 ? titleY + 160 : Math.min(window.innerHeight, 760);
                const images = Array.from(document.querySelectorAll('img')).filter(isVisible);
                const imgBoxes = images.map((el) => {
                    const r = el.getBoundingClientRect();
                    return {
                        width: Math.round(r.width), height: Math.round(r.height), top: Math.round(r.top),
                        naturalWidth: Number(el.naturalWidth || 0), naturalHeight: Number(el.naturalHeight || 0)
                    };
                });
                const largeTopImages = imgBoxes.filter((r) =>
                    r.width >= 420 && r.height >= 140 && r.top < topLimit && r.top > -500 &&
                    r.naturalWidth >= 600 && r.naturalHeight >= 200
                );
                const backgrounds = Array.from(document.querySelectorAll('body *')).filter((el) => {
                    if (!isVisible(el)) return false;
                    const r = el.getBoundingClientRect();
                    if (!(r.width >= 420 && r.height >= 140 && r.top < topLimit && r.top > -500)) return false;
                    const bg = window.getComputedStyle(el).backgroundImage;
                    return Boolean(bg && bg !== 'none');
                }).map((el) => {
                    const r = el.getBoundingClientRect();
                    return {width: Math.round(r.width), height: Math.round(r.height), top: Math.round(r.top)};
                });
                const pictureCount = Array.from(document.querySelectorAll('picture')).filter(isVisible).length;
                const maxMediaWidth = Math.max(0, ...largeTopImages.map((r) => r.width), ...backgrounds.map((r) => r.width));
                const maxMediaHeight = Math.max(0, ...largeTopImages.map((r) => r.height), ...backgrounds.map((r) => r.height));
                return {
                    visible_img_count: images.length,
                    large_top_img_count: largeTopImages.length,
                    large_top_background_count: backgrounds.length,
                    visible_picture_count: pictureCount,
                    max_top_media_width: maxMediaWidth,
                    max_top_media_height: maxMediaHeight,
                    viewport_width: Math.round(window.innerWidth || 0),
                    viewport_height: Math.round(window.innerHeight || 0)
                };
            }""",
            title_y,
        )
        if not isinstance(geometry, dict):
            geometry = {}
    except Exception:
        geometry = {}

    metrics: dict[str, Any] = {
        "eyecatch_exact_control_count": exact_count,
        "eyecatch_exact_control_visible_count": exact_visible,
        "image_labeled_control_count": generic_count,
        "image_labeled_control_visible_count": generic_visible,
        "image_add_control_count": add_count,
        "image_add_control_visible_count": add_visible,
        "file_input_count": file_input_count,
        "title_geometry_available": title_box is not None,
    }
    for key in (
        "visible_img_count",
        "large_top_img_count",
        "large_top_background_count",
        "visible_picture_count",
        "max_top_media_width",
        "max_top_media_height",
        "viewport_width",
        "viewport_height",
    ):
        try:
            metrics[key] = int(geometry.get(key, 0) or 0)
        except Exception:
            metrics[key] = 0
    return metrics


def _classify_eyecatch_state(metrics: dict[str, Any]) -> str:
    media_count = int(metrics.get("large_top_img_count", 0) or 0) + int(
        metrics.get("large_top_background_count", 0) or 0
    )
    exact_visible = int(metrics.get("eyecatch_exact_control_visible_count", 0) or 0)
    generic_visible = int(metrics.get("image_labeled_control_visible_count", 0) or 0)
    add_visible = int(metrics.get("image_add_control_visible_count", 0) or 0)

    if media_count > 0 and exact_visible == 0:
        return "eyecatch_present_selector_drift_likely"
    if media_count == 0 and add_visible > 0:
        return "eyecatch_missing_likely"
    if media_count == 0 and generic_visible == 0:
        return "eyecatch_missing_or_ui_ambiguous"
    if media_count == 0 and generic_visible > 0:
        return "eyecatch_control_without_media_proof"
    return "eyecatch_state_ambiguous"


def _diagnostic_audit_wrapper(original: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    def wrapped(page: Any, title: str, manuscript: str) -> dict[str, Any]:
        try:
            return original(page, title, manuscript)
        except base.PrivateDraftAuditError as exc:
            if str(exc) != EYECATCH_GUARD_MESSAGE:
                raise
            metrics = _safe_header_media_metrics(page)
            code = _classify_eyecatch_state(metrics)
            raise Run294EyecatchDiagnosticError(code, metrics) from None

    return wrapped


def run(*, confirm: str, sync_id: str, prepare_only: bool = False) -> dict[str, Any]:
    original = base._audit_current_page
    base._audit_current_page = _diagnostic_audit_wrapper(original)
    try:
        return base292.run(confirm=confirm, sync_id=sync_id, prepare_only=prepare_only)
    finally:
        base._audit_current_page = original


def _safe_failure_result(sync_id: str, code: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    return base292._safe_failure_result(sync_id, code, metrics)


def _write_result(path_value: str, result: dict[str, Any]) -> None:
    if not path_value:
        return
    target = Path(path_value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", default=os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    parser.add_argument("--confirm", default=os.environ.get("NOTE_AUDIT_CONFIRM", ""))
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        default=os.environ.get("NOTE_AUDIT_PREPARE_ONLY", "false").lower() in {"1", "true", "yes", "on"},
    )
    parser.add_argument("--result-file", default=os.environ.get("NOTE_AUDIT_RESULT_FILE", ""))
    args = parser.parse_args()

    exit_code = 0
    try:
        result = run(confirm=args.confirm, sync_id=args.sync_id, prepare_only=args.prepare_only)
    except Run294EyecatchDiagnosticError as exc:
        result = _safe_failure_result(args.sync_id, exc.code, exc.safe_metrics)
        exit_code = 2
    except base292.Run292AuditDiagnosticError as exc:
        result = _safe_failure_result(args.sync_id, exc.code, exc.safe_metrics)
        exit_code = 2
    except base.PrivateDraftAuditError as exc:
        result = _safe_failure_result(args.sync_id, base292._safe_non_body_guard_code(exc))
        exit_code = 2

    _write_result(args.result_file, result)
    print(json.dumps(result, ensure_ascii=False))
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
