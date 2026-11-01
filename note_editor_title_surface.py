#!/usr/bin/env python3
"""Evidence-only title-surface probe for an authenticated private note editor.

Run908: observe the existing editor without changing selectors or treating
a visible matching title as proof that a draft passed the publication contract.
Only bounded counts and fixed categorical values cross the browser boundary.
No URL, title text, body, DOM HTML, screenshot, cookie, or image data is returned.
"""
from __future__ import annotations

from typing import Any

_COUNT_KEYS = (
    "title_probe_legacy_total",
    "title_probe_legacy_visible",
    "title_probe_editable_visible",
    "title_probe_heading_visible",
    "title_probe_exact_editable_visible",
    "title_probe_exact_heading_visible",
    "title_probe_exact_leaf_visible",
    "title_probe_loading_visible",
    "title_probe_body_elements",
)
_READY_STATES = {"loading", "interactive", "complete"}
_MAX_OUTPUT_COUNT = 20

# These are the six EXISTING selectors in note_draft_automation._find_title.
# The probe is evidence only; it cannot change the production title matcher.
_LEGACY_TITLE_SELECTORS = (
    'textarea[placeholder*="タイトル"], input[placeholder*="タイトル"], '
    '[data-testid="note-title"], [aria-label*="タイトル"], '
    'div[data-placeholder*="タイトル"], h1[contenteditable="true"]'
)


def collect_title_surface_metrics(page: Any, expected_title: str) -> dict[str, Any]:
    """Return a strict, content-free snapshot only after account/route proof."""
    unavailable = {
        "title_probe_status": "unavailable",
        "title_probe_ready_state": "unknown",
    }
    try:
        observation = page.evaluate(
            """([expected, legacySelector]) => {
                const limit = (n) => Math.min(20, Math.max(0, n));
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' &&
                           style.visibility !== 'hidden' &&
                           style.opacity !== '0' &&
                           rect.width > 1 && rect.height > 1;
                };
                const all = (selector) => Array.from(document.querySelectorAll(selector));
                const shown = (elements) => elements.filter(visible);
                const exact = (element) => {
                    const tag = element.tagName.toLowerCase();
                    const value = tag === 'input' || tag === 'textarea'
                        ? String(element.value || '')
                        : String(element.textContent || '');
                    return value.trim() === expected.trim();
                };
                const legacy = all(legacySelector);
                const editable = shown(all('input, textarea, [contenteditable="true"], [role="textbox"]'));
                const headings = shown(all('h1,h2'));
                const elements = all('body *');
                const leaves = elements.slice(0, 3000).filter(
                    (element) => element.children.length === 0 && visible(element)
                );
                const loaders = shown(all('[aria-busy="true"],[role="progressbar"]'));
                return {
                    title_probe_ready_state: String(document.readyState || 'unknown'),
                    title_probe_legacy_total: limit(legacy.length),
                    title_probe_legacy_visible: limit(shown(legacy).length),
                    title_probe_editable_visible: limit(editable.length),
                    title_probe_heading_visible: limit(headings.length),
                    title_probe_exact_editable_visible: limit(editable.filter(exact).length),
                    title_probe_exact_heading_visible: limit(headings.filter(exact).length),
                    title_probe_exact_leaf_visible: limit(leaves.filter(exact).length),
                    title_probe_loading_visible: limit(loaders.length),
                    title_probe_body_elements: limit(elements.length)
                };
            }""",
            [str(expected_title or ""), _LEGACY_TITLE_SELECTORS],
        )
    except Exception:
        return unavailable

    if not isinstance(observation, dict):
        return unavailable
    ready = observation.get("title_probe_ready_state")
    if type(ready) is not str or ready not in _READY_STATES:
        return unavailable
    result: dict[str, Any] = {
        "title_probe_status": "observed",
        "title_probe_ready_state": ready,
    }
    for key in _COUNT_KEYS:
        value = observation.get(key)
        # Reject strings, booleans, negative values, and surprising large numbers.
        if type(value) is not int or not 0 <= value <= _MAX_OUTPUT_COUNT:
            return unavailable
        result[key] = value
    return result
