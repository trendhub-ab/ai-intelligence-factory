#!/usr/bin/env python3
"""Shared, fail-closed proof that note kept the draft eyecatch.

The note editor has changed its header-image controls over time. A visible legacy
"画像を変更" button remains strong evidence, but Run294 proved that current note can
retain the eyecatch while that button no longer exists. This module therefore uses
only non-content DOM evidence:

- a visible legacy change-image control; OR
- a large, natural-size media element near the title while no visible add-image
  control is present.

It never reads image URLs/src values, DOM HTML, unpublished article text, or browser
storage. It contains no click/fill/upload/save/screenshot/network/model/publication
surface.
"""
from __future__ import annotations

from typing import Any


LEGACY_CONTROL_SELECTOR = (
    'button[aria-label="画像を変更"], button[aria-label*="見出し画像を変更"]'
)
GENERIC_IMAGE_CONTROL_SELECTOR = (
    'button[aria-label*="画像"], [role="button"][aria-label*="画像"]'
)
ADD_IMAGE_CONTROL_SELECTOR = (
    'button[aria-label="画像を追加"], button[aria-label*="見出し画像"], '
    'button:has-text("画像を追加")'
)

PRESENT_LEGACY_CONTROL = "eyecatch_present_legacy_control"
PRESENT_HEADER_MEDIA = "eyecatch_present_header_media"
MISSING_LIKELY = "eyecatch_missing_likely"
AMBIGUOUS = "eyecatch_persistence_ambiguous"


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


def _title_box(title_locator: Any | None) -> dict[str, float] | None:
    if title_locator is None:
        return None
    try:
        raw = title_locator.bounding_box()
    except Exception:
        return None
    if not raw:
        return None
    try:
        return {
            "x": float(raw.get("x", 0)),
            "y": float(raw.get("y", 0)),
            "width": float(raw.get("width", 0)),
            "height": float(raw.get("height", 0)),
        }
    except Exception:
        return None


def collect_eyecatch_metrics(page: Any, *, title_locator: Any | None = None) -> dict[str, Any]:
    """Collect only counts/visibility/geometry needed for eyecatch persistence proof."""
    title_box = _title_box(title_locator)
    title_y = float((title_box or {}).get("y", -1))

    exact = page.locator(LEGACY_CONTROL_SELECTOR)
    generic = page.locator(GENERIC_IMAGE_CONTROL_SELECTOR)
    add_controls = page.locator(ADD_IMAGE_CONTROL_SELECTOR)
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


def classify_eyecatch_persistence(metrics: dict[str, Any]) -> str:
    media_count = int(metrics.get("large_top_img_count", 0) or 0) + int(
        metrics.get("large_top_background_count", 0) or 0
    )
    exact_visible = int(metrics.get("eyecatch_exact_control_visible_count", 0) or 0)
    add_visible = int(metrics.get("image_add_control_visible_count", 0) or 0)

    if exact_visible > 0:
        return PRESENT_LEGACY_CONTROL
    if media_count > 0 and add_visible == 0:
        return PRESENT_HEADER_MEDIA
    if media_count == 0 and add_visible > 0:
        return MISSING_LIKELY
    return AMBIGUOUS


def eyecatch_persistence_confirmed(metrics: dict[str, Any]) -> bool:
    return classify_eyecatch_persistence(metrics) in {PRESENT_LEGACY_CONTROL, PRESENT_HEADER_MEDIA}


class _ConfirmedLegacyLocator:
    """Minimal Playwright-like locator used only to satisfy the obsolete legacy check."""

    @property
    def first(self) -> "_ConfirmedLegacyLocator":
        return self

    def count(self) -> int:
        return 1

    def is_visible(self, *args: Any, **kwargs: Any) -> bool:
        return True


class EyecatchProofPageProxy:
    """Delegate a page while translating current proof into the legacy control contract."""

    def __init__(self, page: Any, title_locator_factory: Any) -> None:
        self._page = page
        self._title_locator_factory = title_locator_factory

    def _confirmed(self) -> bool:
        try:
            title_locator = self._title_locator_factory(self._page)
        except Exception:
            title_locator = None
        metrics = collect_eyecatch_metrics(self._page, title_locator=title_locator)
        return eyecatch_persistence_confirmed(metrics)

    def locator(self, selector: str, *args: Any, **kwargs: Any) -> Any:
        if str(selector) == LEGACY_CONTROL_SELECTOR and self._confirmed():
            return _ConfirmedLegacyLocator()
        return self._page.locator(selector, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._page, name)


def install_creation_persistence_guard(note_base: Any) -> None:
    """Patch the current creation path to require shared proof after draft reload.

    The legacy save function remains responsible for title/body persistence. The proxy
    prevents a current, proven header image from being rejected solely because note
    renamed its old control. A second postcondition then closes the historic count()==0
    escape hatch: no shared evidence means the draft never advances.
    """
    original = note_base._save_draft_and_verify
    if getattr(original, "_run295_shared_eyecatch_guard", False):
        return

    def guarded(page: Any, title: str, manuscript: str, image_required: bool = True) -> str:
        proxy = EyecatchProofPageProxy(page, note_base._find_title)
        draft_url = original(proxy, title, manuscript, image_required=image_required)
        if image_required:
            try:
                title_locator = note_base._find_title(page)
            except Exception:
                title_locator = None
            metrics = collect_eyecatch_metrics(page, title_locator=title_locator)
            if not eyecatch_persistence_confirmed(metrics):
                raise note_base.NoteDraftError("note eyecatch persistence verification failed")
        return draft_url

    guarded._run295_shared_eyecatch_guard = True
    guarded._run295_original = original
    note_base._save_draft_and_verify = guarded
