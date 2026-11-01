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
    "title_probe_main_visible",
    "title_probe_app_root_count",
    "title_probe_alert_visible",
    "title_probe_form_visible",
    "title_probe_password_visible",
    "title_probe_iframe_count",
    "title_probe_script_count",
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


def navigation_status_category(response: Any) -> str:
    """Classify only the main-document HTTP status; never inspect headers or URLs."""
    if response is None:
        return "no_response"
    try:
        status = response.status
    except Exception:
        return "unknown"
    if type(status) is not int or not 100 <= status <= 599:
        return "unknown"
    if status == 401:
        return "http_401"
    if status == 403:
        return "http_403"
    if status == 404:
        return "http_404"
    if 200 <= status < 300:
        return "http_2xx"
    if 300 <= status < 400:
        return "http_3xx"
    if 400 <= status < 500:
        return "http_4xx_other"
    if 500 <= status < 600:
        return "http_5xx"
    return "http_other"


def _shell_classification(metrics: dict[str, Any]) -> str:
    """Observation labels are not evidence of a healthy or failed note app."""
    if metrics["title_probe_alert_visible"] > 0:
        return "alert_marker"
    if metrics["title_probe_loading_visible"] > 0:
        return "loading_marker"
    if metrics["title_probe_editable_visible"] > 0:
        return "other_editables"
    if metrics["title_probe_app_root_count"] > 0:
        return "app_root_no_editables"
    if metrics["title_probe_main_visible"] > 0:
        return "main_no_editables"
    return "no_visible_editor_markers"


def collect_title_surface_metrics(
    page: Any, expected_title: str, *, navigation_response: Any = None
) -> dict[str, Any]:
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
                const mains = shown(all('main,[role="main"]'));
                const roots = all('#__next,#app,#root');
                const alerts = shown(all('[role="alert"],[aria-invalid="true"]'));
                const forms = shown(all('form'));
                const passwords = shown(all('input[type="password"]'));
                const frames = all('iframe');
                const scripts = all('script');
                const bucket = elements.length === 0 ? 'empty' :
                               elements.length <= 20 ? 'small' :
                               elements.length <= 200 ? 'medium' : 'large';
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
                    title_probe_body_elements: limit(elements.length),
                    title_probe_body_size_class: bucket,
                    title_probe_main_visible: limit(mains.length),
                    title_probe_app_root_count: limit(roots.length),
                    title_probe_alert_visible: limit(alerts.length),
                    title_probe_form_visible: limit(forms.length),
                    title_probe_password_visible: limit(passwords.length),
                    title_probe_iframe_count: limit(frames.length),
                    title_probe_script_count: limit(scripts.length)
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
    size_class = observation.get("title_probe_body_size_class")
    if type(size_class) is not str or size_class not in {"empty", "small", "medium", "large"}:
        return unavailable
    for key in _COUNT_KEYS:
        value = observation.get(key)
        # Reject strings, booleans, negative values, and surprising large numbers.
        if type(value) is not int or not 0 <= value <= _MAX_OUTPUT_COUNT:
            return unavailable
        result[key] = value
    result["title_probe_body_size_class"] = size_class
    result["title_probe_navigation_status"] = navigation_status_category(navigation_response)
    result["title_probe_shell_class"] = _shell_classification(result)
    return result
