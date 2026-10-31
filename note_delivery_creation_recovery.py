#!/usr/bin/env python3
"""Read-only discovery for a P0-B CREATION_UNKNOWN private draft.

This module never changes the durable ledger, Notion queue, or note draft. It is only a
manual-reconciliation evidence collector for the narrow crash window where note may have
accepted a private draft but the stable edit-route identity was not durably recorded.

The exact sync ID and recovered draft identity are runner-private. Standard output exposes
only a safe operational projection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from urllib.parse import urlsplit, urlparse, urljoin, parse_qs
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from unittest.mock import patch

import note_delivery_runtime as delivery_runtime
import note_document_contract as note_contract
import note_document_dom as note_dom
import note_publication_reconcile as reconcile
import run187_note_editor_readiness as editor_readiness
import run190_note_persistent_cloud as cloud
import run194_note_current_contract as current_contract
import run222_note_presentation_integrity as presentation
import run291_note_private_draft_audit as draft_audit
from note_delivery_ledger import (
    DeliveryRecord,
    DeliveryState,
    SQLiteDeliveryLedger,
    canonical_document_sha256,
)


CONFIRM_TOKEN = "AUDIT_CREATION_UNKNOWN"

# Only aggregate counts are exposed; never expose candidate URLs, titles or draft IDs.
REJECTION_BUCKETS = (
    "logged_out", "non_editor", "different_title",
    "content_or_eyecatch", "canonical_hash", "inspection_error",
)
# Fixed stage labels only; never log exception texts, candidate URLs or article text.
INSPECTION_STAGES = (
    "navigation", "login_check", "editor_route", "title_read",
    "body_audit", "canonical_read", "identity_read", "other",
)
# Fixed aggregate reasons for title-read exceptions only. No page/exception content.
TITLE_FAILURE_CODES = (
    "title_selector_unavailable", "title_selector_exception",
    "title_retry_interrupted", "title_value_unreadable", "title_other",
)
# Independent aggregate DOM presence signals for confirmed existing editor routes.
# Never record page identity, raw HTML, text, attributes, counts or error messages.
TITLE_DOM_SIGNAL_CODES = (
    "ready_loading", "ready_interactive", "ready_complete", "ready_unknown",
    "body_present", "body_missing", "body_unknown",
    "inputs_present", "inputs_missing", "inputs_unknown",
    "editables_present", "editables_missing", "editables_unknown",
    "textboxes_present", "textboxes_missing", "textboxes_unknown",
    "busy_present", "busy_missing", "busy_unknown",
)
# High-level response, stable private identity, browser and login-marker signals.
# Counts only: do not emit URLs, opaque IDs, session data or raw exceptions.
TITLE_CONTEXT_CODES = (
    "http_2xx", "http_3xx", "http_4xx", "http_5xx", "http_unknown",
    "route_same_identity", "route_other_identity", "route_unverified",
    "browser_open", "browser_closed", "browser_unknown",
    "js_responding", "js_unavailable",
    "login_markers_present", "login_markers_absent", "login_markers_unknown",
)
# Candidate-specific values never leave memory. These are only fixed aggregate signals.
TITLE_ROUTE_SHAPES = (
    "shape_strict_supported", "shape_query_or_fragment", "shape_www_host",
    "shape_non_https", "shape_other_path", "shape_invalid_identity",
    "shape_other_host", "shape_unknown",
)
TITLE_ATOMIC_DOM_CODES = (
    "atomic_available", "atomic_unavailable",
    "atomic_ready_complete", "atomic_ready_interactive",
    "atomic_ready_loading", "atomic_ready_unknown",
    "atomic_body_present", "atomic_body_missing", "atomic_body_unknown",
    "atomic_inputs_present", "atomic_inputs_missing", "atomic_inputs_unknown",
    "atomic_editables_present", "atomic_editables_missing", "atomic_editables_unknown",
    "atomic_textboxes_present", "atomic_textboxes_missing", "atomic_textboxes_unknown",
    "atomic_busy_present", "atomic_busy_missing", "atomic_busy_unknown",
)
# Read rendered page text only inside note's private VM and return an integer
# evidence bitmask; never log, persist, upload, or return text/screenshots/IDs.
# Hints are not definitive proof of authentication, authorization or draft absence.
SCREEN_SIGNAL_CODES = (
    "surface_not_found_hint", "surface_permission_hint",
    "surface_login_required_hint", "surface_error_or_retry_hint",
    "surface_header_present", "surface_main_present",
    "surface_button_present", "surface_frame_present",
    "surface_dialog_present", "surface_alert_present",
    "surface_short_visible_text", "surface_editor_link_present",
    "surface_app_mount_present", "surface_no_indicators",
    "surface_probe_unavailable",
)
# Aggregate official-note-list evidence codes. No private title or ID in output.
OFFICIAL_LIST_CODES = (
    "account_unverified", "account_proven",
    "list_unavailable", "list_open",
    "title_button_uninspectable", "title_button_not_visible",
    "title_button_ambiguous", "title_button_unique",
    "edit_navigation_failed", "editor_route_unverified",
    "editor_route_verified", "editor_in_history", "editor_not_in_history",
    "editor_title_unreadable", "editor_title_mismatch", "editor_title_equal",
    "body_eyecatch_unverified", "body_eyecatch_equal",
    "canonical_unverified", "canonical_mismatch", "canonical_equal",
)
OFFICIAL_LIST_SCAN_CODES = (
    "list_draft_filter_visible", "list_draft_filter_active",
    "list_more_control_visible", "list_pagination_visible",
    "list_scroll_attempted", "list_scroll_no_motion",
    "list_title_found_after_scroll", "list_pagination_followed",
    "list_scan_limit_reached", "list_scan_unavailable",
    # Browser-private structural evidence only; never identity or raw DOM.
    "list_root_scrollable", "list_nested_scrollable",
    "list_main_populated", "list_any_edit_control",
    "list_loading_visible", "list_scroll_overflow_hidden",
    # Observed authenticated same-origin API GET traffic only; no endpoint guessing.
    "api_get_observed", "api_json_readable", "api_target_title_seen",
    "api_json_unreadable", "api_response_oversize", "api_http_non_success",
    "api_capture_limit",
    # Fixed-code response diagnostics. Names and IDs are never emitted.
    "api_path_article_hint", "api_path_account_hint", "api_path_other",
    "api_http_auth_denied", "api_http_not_found", "api_http_rate_limited",
    "api_http_server_error", "api_http_other_non_success",
    "api_root_object", "api_root_array", "api_title_field_seen",
    "api_nested_collection_seen", "api_empty_collection_seen",
    "api_pagination_hint",
    # Read-only owner-draft view; no proof of draft absence from incomplete UI.
    "list_draft_view_open", "list_draft_route_unverified",
    "list_draft_view_unavailable", "list_draft_structure_unavailable",
    "list_draft_title_unique", "list_draft_title_ambiguous",
    "list_draft_title_not_visible", "list_self_articles_nav_visible",
    "list_draft_filter_nav_visible", "list_draft_filter_selected",
    "list_draft_any_edit_control",
    # Authenticated real-DOM menu/card shape; never raw text, links or IDs.
    "list_owner_nav_anchor", "list_owner_nav_button",
    "list_owner_nav_note_href", "list_title_exact_anchor",
    "list_title_exact_plain_text", "list_existing_edit_href",
    "list_article_card_present", "list_profile_menu_trigger",
    "list_main_content_populated", "list_empty_or_error_notice",
    "list_loading_placeholder", "list_embedded_frame",
    # Same-account visible owner-menu route versus direct URL, fixed codes only.
    "menu_origin_unverified", "menu_link_exact", "menu_link_missing",
    "menu_link_ambiguous", "menu_link_uninspectable", "menu_link_rejected",
    "menu_trigger_unique", "menu_trigger_missing", "menu_trigger_ambiguous",
    "menu_opened", "menu_open_failed", "menu_route_open",
    "menu_route_unverified", "menu_route_unavailable",
    "menu_route_main_populated", "menu_route_article_card_present",
    "menu_route_edit_control_present", "menu_route_title_visible",
    "menu_route_draft_filter_visible", "menu_route_loading",
    # Verified note home, private fixed-bit DOM signature and observed own-articles link.
    "home_open", "home_route_unverified", "home_unavailable",
    "home_dom_uninspectable", "home_main_populated",
    "home_creator_profile_link_visible", "home_avatar_button_visible",
    "home_profile_menu_trigger_visible", "home_owner_article_link_visible",
    "home_owner_article_link_hidden", "home_draft_link_visible",
    "home_article_card_visible", "home_loading_visible",
    "home_profile_label_visible", "home_header_visible",
    "home_avatar_image_visible", "home_avatar_svg_button_visible",
    "home_post_dropdown_visible", "home_owner_link_missing",
    "home_owner_link_uninspectable", "home_owner_link_ambiguous",
    "home_owner_link_rejected", "home_owner_link_exact",
    "home_owner_route_open", "home_owner_route_unverified",
    "home_owner_route_unavailable", "home_owner_route_main_populated",
    "home_owner_route_article_card_present",
    "home_owner_route_edit_control_present",
    # One-way, allowlisted diagnostics for SVG buttons on verified note home.
    "home_svg_context_uninspectable", "home_svg_header_unique",
    "home_svg_header_multiple", "home_svg_outside_header",
    "home_svg_header_account_name_hint", "home_svg_header_search_name_hint",
    "home_svg_header_notification_name_hint", "home_svg_header_compose_name_hint",
    "home_svg_header_menu_semantics", "home_svg_header_unlabeled",
    "home_svg_header_image_child", "home_svg_guest_login_visible",
    "home_svg_guest_signup_visible", "home_svg_header_icon_link_visible",
    "home_svg_header_profile_link_visible",
)


class CreationRecoveryAuditError(RuntimeError):
    pass


class TitleReadInspectionError(RuntimeError):
    """An explicitly allowlisted, content-free reason code for audit counters."""

    def __init__(self, code: str) -> None:
        if code not in TITLE_FAILURE_CODES:
            raise ValueError("title inspection code must be allowlisted")
        self.code = code
        super().__init__(code)


def _title_failure_code(exc: Exception) -> str:
    if isinstance(exc, TitleReadInspectionError):
        return exc.code
    if isinstance(exc, draft_audit.PrivateDraftAuditError):
        return "title_value_unreadable"
    return "title_other"


def safe_recovery_projection(result: dict[str, Any]) -> dict[str, Any]:
    """Return only fields safe for Actions logs and summaries."""
    return {
        "status": str(result.get("status") or "unknown"),
        "read_only": result.get("read_only") is True,
        "zero_gemini_calls": result.get("zero_gemini_calls") is True,
        "draft_mutation": result.get("draft_mutation") is True,
        "public_release": result.get("public_release") is True,
        "match_count": int(result.get("match_count") or 0),
        "history_candidate_count": int(result.get("history_candidate_count") or 0),
        "editor_route_hash": str(result.get("editor_route_hash") or ""),
        "rejection_counts": {
            bucket: int((result.get("rejection_counts") or {}).get(bucket) or 0)
            for bucket in REJECTION_BUCKETS
        },
        "inspection_stage_counts": {
            stage: int((result.get("inspection_stage_counts") or {}).get(stage) or 0)
            for stage in INSPECTION_STAGES
        },
        "title_failure_counts": {
            code: int((result.get("title_failure_counts") or {}).get(code) or 0)
            for code in TITLE_FAILURE_CODES
        },
        "title_dom_signal_counts": {
            code: int((result.get("title_dom_signal_counts") or {}).get(code) or 0)
            for code in TITLE_DOM_SIGNAL_CODES
        },
        "title_context_signal_counts": {
            code: int((result.get("title_context_signal_counts") or {}).get(code) or 0)
            for code in TITLE_CONTEXT_CODES
        },
        "title_route_shape_counts": {
            code: int((result.get("title_route_shape_counts") or {}).get(code) or 0)
            for code in TITLE_ROUTE_SHAPES
        },
        "title_atomic_dom_counts": {
            code: int((result.get("title_atomic_dom_counts") or {}).get(code) or 0)
            for code in TITLE_ATOMIC_DOM_CODES
        },
        "failed_screen_signal_counts": {
            code: int((result.get("failed_screen_signal_counts") or {}).get(code) or 0)
            for code in SCREEN_SIGNAL_CODES
        },
        "control_screen_signal_counts": {
            code: int((result.get("control_screen_signal_counts") or {}).get(code) or 0)
            for code in SCREEN_SIGNAL_CODES
        },
        "official_list_proof_counts": {
            code: int((result.get("official_list_proof_counts") or {}).get(code) or 0)
            for code in OFFICIAL_LIST_CODES
        },
        "official_list_scan_counts": {
            code: int((result.get("official_list_scan_counts") or {}).get(code) or 0)
            for code in OFFICIAL_LIST_SCAN_CODES
        },
    }


def _read_logical_record_read_only(
    ledger: SQLiteDeliveryLedger,
    *,
    logical_key: str,
) -> DeliveryRecord | None:
    path = Path(ledger.path).expanduser()
    if not path.is_file():
        raise CreationRecoveryAuditError("durable delivery ledger is unavailable")
    try:
        conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only=ON")
            row = conn.execute(
                "SELECT d.* FROM logical_bindings b JOIN deliveries d "
                "ON d.operation_key=b.operation_key WHERE b.logical_key=?",
                (logical_key,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise CreationRecoveryAuditError("durable delivery ledger read failed") from exc
    return SQLiteDeliveryLedger._row_to_record(row) if row is not None else None


def require_creation_unknown_record(
    ledger: SQLiteDeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
) -> DeliveryRecord:
    """Require exactly the ambiguous no-identity state that may be discovered read-only."""
    logical_key = delivery_runtime._logical_key_for_identity(sync_id, note_target)
    record = _read_logical_record_read_only(ledger, logical_key=logical_key)
    if record is None:
        raise CreationRecoveryAuditError("no durable logical delivery exists for recovery")
    if record.state != DeliveryState.CREATION_UNKNOWN:
        raise CreationRecoveryAuditError("durable delivery is not CREATION_UNKNOWN")
    if str(record.draft_id or "").strip():
        raise CreationRecoveryAuditError("ambiguous delivery already has a stable draft identity")
    return record


def require_unique_recovery_match(matches: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(matches)
    if len(items) != 1:
        raise CreationRecoveryAuditError("private draft recovery did not produce exactly one verified match")
    return dict(items[0])


def _expected_prepared_delivery(record: DeliveryRecord) -> delivery_runtime.PreparedDelivery:
    """Rebuild the current delivery and require exact equality with the ambiguous attempt."""
    current_contract.install()
    presentation.install_note(current_contract.base)

    previous_target = os.environ.get("NOTE_TARGET_IDENTITY")
    os.environ["NOTE_TARGET_IDENTITY"] = record.snapshot.note_target
    try:
        try:
            prepared = delivery_runtime.prepare_delivery(
                current_contract.base,
                record.snapshot.sync_id,
            )
        except Exception as exc:
            raise CreationRecoveryAuditError(
                "current publication-contract target is not recoverable"
            ) from exc
    finally:
        if previous_target is None:
            os.environ.pop("NOTE_TARGET_IDENTITY", None)
        else:
            os.environ["NOTE_TARGET_IDENTITY"] = previous_target

    if prepared.snapshot != record.snapshot:
        raise CreationRecoveryAuditError(
            "current delivery snapshot differs from the ambiguous creation attempt"
        )
    article = dict(prepared.article)
    if not str(article.get("title") or "").strip() or not str(article.get("manuscript") or "").strip():
        raise CreationRecoveryAuditError("current publication-contract target is incomplete")
    return prepared


def _current_canonical_sha256(page: Any) -> str:
    """Read the editor DOM through the same lossless semantic path used by P0-A."""
    try:
        title_field = draft_audit.note_base._find_title(page)
        body = draft_audit.note_base._find_body(page, title_field)
        snapshot = note_dom.snapshot_note_body(body)
        document = note_dom.document_from_note_snapshot(
            snapshot,
            allowed_normalizations=(
                note_contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,
                note_dom.NOTE_BLOCKQUOTE_FIGURE_WRAPPER,
            ),
        )
        return canonical_document_sha256(document)
    except Exception as exc:
        raise CreationRecoveryAuditError("private draft canonical body is unavailable") from exc


def _read_only_title_field(page: Any, legacy_finder: Any) -> Any:
    """Use the existing explicit title selector without editor entry or DOM mutation.

    The historical editor may use a newer explicit attribute than the legacy
    finder recognizes. This fallback only reads a currently loaded editor page;
    no geometric guessing, navigation, text mutation, or new draft creation.
    """
    if not editor_readiness._is_editor_url(str(page.url or "")):
        raise CreationRecoveryAuditError("existing private editor route is not confirmed")
    try:
        return legacy_finder(page)
    except Exception:
        explicit_error = False
        for _ in range(3):
            try:
                field = editor_readiness._explicit_title(page)
            except Exception:
                explicit_error = True
                field = None
            if field is not None:
                return field
            try:
                page.wait_for_timeout(450)
            except Exception:
                raise TitleReadInspectionError("title_retry_interrupted") from None
        code = "title_selector_exception" if explicit_error else "title_selector_unavailable"
        raise TitleReadInspectionError(code) from None


def _safe_title_dom_signals(page: Any) -> tuple[str, ...]:
    """Read only boolean DOM presence / bounded readiness codes on an edit route.

    No page content, title strings, editor URL, raw selector counts, HTML, screenshot
    or arbitrary browser exception enters the result or logs. These probes never
    create a title candidate or authorize recovery.
    """
    unknown = (
        "ready_unknown", "body_unknown", "inputs_unknown",
        "editables_unknown", "textboxes_unknown", "busy_unknown",
    )
    if not editor_readiness._is_editor_url(str(page.url or "")):
        return unknown

    try:
        state = page.evaluate("document.readyState")
        ready = {
            "loading": "ready_loading",
            "interactive": "ready_interactive",
            "complete": "ready_complete",
        }.get(state, "ready_unknown") if isinstance(state, str) else "ready_unknown"
    except Exception:
        ready = "ready_unknown"

    signals = [ready]
    for category, selector in (
        ("body", "body"),
        ("inputs", "input, textarea"),
        ("editables", '[contenteditable="true"], [contenteditable="plaintext-only"]'),
        ("textboxes", '[role="textbox"]'),
        ("busy", '[role="progressbar"], [aria-busy="true"]'),
    ):
        try:
            present = int(page.locator(selector).count()) > 0
            signals.append(f"{category}_{'present' if present else 'missing'}")
        except Exception:
            signals.append(f"{category}_unknown")
    return tuple(signals)


def _safe_title_context_signals(page: Any, requested_url: str, response: Any) -> tuple[str, ...]:
    """Only classify pre-existing navigation and browser state, never read content.

    HTTP response is the existing page.goto return value; no additional request.
    Route comparison uses private IDs only in memory; output contains a fixed code.
    Missing login markers do NOT prove an authenticated session.
    """
    try:
        status = response.status
        if not isinstance(status, int) or isinstance(status, bool):
            http = "http_unknown"
        elif 200 <= status < 300:
            http = "http_2xx"
        elif 300 <= status < 400:
            http = "http_3xx"
        elif 400 <= status < 500:
            http = "http_4xx"
        elif 500 <= status < 600:
            http = "http_5xx"
        else:
            http = "http_unknown"
    except Exception:
        http = "http_unknown"

    try:
        expected_id = reconcile.draft_identity_from_url(requested_url)
        observed_id = reconcile.draft_identity_from_url(str(page.url or ""))
        route = "route_same_identity" if expected_id == observed_id else "route_other_identity"
    except Exception:
        route = "route_unverified"

    try:
        closed = page.is_closed()
        browser = "browser_closed" if closed is True else (
            "browser_open" if closed is False else "browser_unknown"
        )
    except Exception:
        browser = "browser_unknown"

    if browser == "browser_closed":
        js = "js_unavailable"
    else:
        try:
            js = "js_responding" if page.evaluate("1") == 1 else "js_unavailable"
        except Exception:
            js = "js_unavailable"

    try:
        logged_out = draft_audit.note_base._looks_logged_out(page)
        login = "login_markers_present" if logged_out else "login_markers_absent"
    except Exception:
        login = "login_markers_unknown"
    return http, route, browser, js, login


def _safe_title_route_shape(url: str) -> str:
    """Classify a URL's format without returning its host, path or identity.

    This does not validate a draft, normalize a URL for use, or override the
    strict identity validator. Identity is not retained after classification.
    """
    try:
        parsed = urlsplit(str(url or ""))
        if parsed.scheme != "https":
            return "shape_non_https"
        host = (parsed.hostname or "").lower()
        if host == "www.note.com":
            return "shape_www_host"
        if host not in {"note.com", "editor.note.com"}:
            return "shape_other_host"
        if parsed.query or parsed.fragment:
            return "shape_query_or_fragment"
        match = re.fullmatch(r"/notes/([^/]+)/edit/?", parsed.path or "")
        if match is None or parsed.username or parsed.password or parsed.port:
            return "shape_other_path"
        identity = match.group(1)
        if len(identity) > 200 or re.fullmatch(r"[A-Za-z0-9_-]+", identity) is None:
            return "shape_invalid_identity"
        return "shape_strict_supported"
    except Exception:
        return "shape_unknown"


def _safe_title_atomic_dom_signals(page: Any) -> tuple[str, ...]:
    """One read-only browser call returning only six fixed DOM boolean signals.

    No HTML/attributes/innerText/URL/title leave the browser. Untrusted result
    keys, types, script failures and browser exception text are never output.
    This probe never supplies a title match or changes the recovery decision.
    """
    try:
        snapshot = page.evaluate("""() => {
            const d = document;
            return {
                ready: d.readyState,
                body: !!d.body,
                inputs: !!d.querySelector('input, textarea'),
                editables: !!d.querySelector('[contenteditable="true"], [contenteditable="plaintext-only"]'),
                textboxes: !!d.querySelector('[role="textbox"]'),
                busy: !!d.querySelector('[role="progressbar"], [aria-busy="true"]')
            };
        }""")
    except Exception:
        return ("atomic_unavailable",)
    if not isinstance(snapshot, dict):
        return ("atomic_unavailable",)
    state = snapshot.get("ready")
    ready = {
        "complete": "atomic_ready_complete",
        "interactive": "atomic_ready_interactive",
        "loading": "atomic_ready_loading",
    }.get(state, "atomic_ready_unknown") if isinstance(state, str) else "atomic_ready_unknown"
    signals = ["atomic_available", ready]
    for name in ("body", "inputs", "editables", "textboxes", "busy"):
        value = snapshot.get(name)
        status = "present" if value is True else ("missing" if value is False else "unknown")
        signals.append(f"atomic_{name}_{status}")
    return tuple(signals)


def _safe_visible_screen_signals(page: Any) -> tuple[str, ...]:
    """Observe the actual rendered browser screen without exporting page content.

    Only a number of preapproved bit flags is returned from the in-browser
    evaluation. Screen text is used solely within that evaluation to detect
    literal user-facing error hints; it is never sent to Python, GitHub logs,
    an external service, artifacts or the result file. No screenshots.
    """
    try:
        mask = page.evaluate(r"""() => {
            const d = document;
            const content = (d.body && typeof d.body.innerText === 'string')
                ? d.body.innerText.slice(0, 12000) : '';
            let mask = 0;
            if (/(ページが見つかりません|お探しのページが見つかりません|404 Not Found|page not found)/i.test(content))
                mask |= 1;
            if (/(権限がありません|アクセス権限|アクセスできません|閲覧できません|公開されていません|削除されました)/i.test(content))
                mask |= 2;
            if (/(ログインしてください|ログインが必要|ログインしてから|ログインしないと)/i.test(content))
                mask |= 4;
            if (/(エラーが発生|読み込みに失敗|しばらく経ってから|もう一度お試し|一時的に利用できません|temporarily unavailable)/i.test(content))
                mask |= 8;
            if (d.querySelector('header, [role="banner"]')) mask |= 16;
            if (d.querySelector('main, [role="main"]')) mask |= 32;
            if (d.querySelector('button, [role="button"]')) mask |= 64;
            if (d.querySelector('iframe')) mask |= 128;
            if (d.querySelector('[role="dialog"], dialog[open]')) mask |= 256;
            if (d.querySelector('[role="alert"], [aria-live="assertive"]')) mask |= 512;
            if (content.trim().length < 25) mask |= 1024;
            if (d.querySelector('a[href="/notes/new"], a[href*="/notes/new"]'))
                mask |= 2048;
            if (d.querySelector('#__next, #root, [data-reactroot]'))
                mask |= 4096;
            return mask;
        }""")
    except Exception:
        return ("surface_probe_unavailable",)
    if isinstance(mask, bool) or not isinstance(mask, int) or not 0 <= mask < (1 << 13):
        return ("surface_probe_unavailable",)
    if mask == 0:
        return ("surface_no_indicators",)
    mapped = (
        "surface_not_found_hint", "surface_permission_hint",
        "surface_login_required_hint", "surface_error_or_retry_hint",
        "surface_header_present", "surface_main_present",
        "surface_button_present", "surface_frame_present",
        "surface_dialog_present", "surface_alert_present",
        "surface_short_visible_text", "surface_editor_link_present",
        "surface_app_mount_present",
    )
    return tuple(code for index, code in enumerate(mapped) if mask & (1 << index))


_MAX_NOTE_API_BODY_BYTES = 512_000
_MAX_NOTE_API_RESPONSES = 12


def _safe_note_api_response_signals(response: Any, target_title: str) -> set[str]:
    """Classify a first-party GET response already observed in the owner VM.

    This helper sends no request and returns only fixed codes. It cannot prove
    that an existing private draft is present or absent, nor authorize writes.
    """
    try:
        parsed = urlsplit(str(response.url or ""))
        if (parsed.scheme != "https" or
            parsed.hostname not in {"note.com", "editor.note.com"} or
            parsed.username or parsed.password or parsed.port is not None or
            not parsed.path.startswith("/api/") or
            str(response.request.method).upper() != "GET"):
            return set()
        segments = {part.lower() for part in parsed.path.split("/")[2:]}
        if segments.intersection({"articles", "article", "notes", "note", "drafts", "draft"}):
            path_hint = "api_path_article_hint"
        elif segments.intersection({"users", "user", "profile", "profiles",
                                    "account", "accounts", "settings", "session", "auth"}):
            path_hint = "api_path_account_hint"
        else:
            path_hint = "api_path_other"
    except Exception:
        return set()

    evidence = {"api_get_observed", path_hint}
    try:
        status = int(response.status)
        if not 200 <= status < 300:
            if status in (401, 403):
                reason = "api_http_auth_denied"
            elif status == 404:
                reason = "api_http_not_found"
            elif status == 429:
                reason = "api_http_rate_limited"
            elif 500 <= status < 600:
                reason = "api_http_server_error"
            else:
                reason = "api_http_other_non_success"
            return evidence | {"api_http_non_success", reason}
        headers = dict(response.headers or {})
        content_type = str(headers.get("content-type") or "").lower().split(";", 1)[0].strip()
        if content_type != "application/json" and not content_type.endswith("+json"):
            return evidence
        length = str(headers.get("content-length") or "")
        if length.isdecimal() and int(length) > _MAX_NOTE_API_BODY_BYTES:
            return evidence | {"api_response_oversize"}
        raw = response.body()
        if not isinstance(raw, bytes) or len(raw) > _MAX_NOTE_API_BODY_BYTES:
            return evidence | {"api_response_oversize"}
        payload = json.loads(raw)
    except Exception:
        return evidence | {"api_json_unreadable"}
    evidence.add("api_json_readable")

    if isinstance(payload, dict):
        evidence.add("api_root_object")
    elif isinstance(payload, list):
        evidence.add("api_root_array")

    # A bounded structural traversal, not an arbitrary dump, network crawl, or
    # identifier extractor. An empty list may belong to unrelated API data.
    nodes = [(payload, 0)]
    seen = 0
    while nodes and seen < 500:
        node, depth = nodes.pop()
        seen += 1
        if isinstance(node, dict):
            if any(key in node for key in (
                "pagination", "next_page", "next", "has_next",
                "hasNext", "total_pages", "next_cursor",
            )):
                evidence.add("api_pagination_hint")
            value = node.get("title")
            if isinstance(value, str):
                evidence.add("api_title_field_seen")
                if value.strip() == target_title.strip():
                    evidence.add("api_target_title_seen")
                    break
            if depth < 6:
                nodes.extend((v, depth + 1) for v in list(node.values())[:500])
        elif isinstance(node, list):
            if len(node) == 0:
                evidence.add("api_empty_collection_seen")
            if any(isinstance(item, dict) for item in node[:500]):
                evidence.add("api_nested_collection_seen")
            if depth < 6:
                nodes.extend((v, depth + 1) for v in node[:500])
    return evidence

def _bounded_official_list_scan(page: Any, title: str) -> set[str]:
    """Bounded observation of an already authenticated note official article list.

    No click, filter selection, form submission, arbitrary route construction or
    private browser text export. Scrolling can reveal lazily loaded list entries.
    Explicit next-page *anchors* are followed only when an HTTPS note.com/notes
    link has one numeric page query; no other queries, hosts or paths are allowed.
    An incomplete scan can NEVER establish absence of a draft.
    """
    evidence: set[str] = set()
    visited = {str(getattr(page, "url", "") or "")}
    try:
        for page_index in range(3):  # at most three actual list pages
            mask = page.evaluate(r"""() => {
                const items = Array.from(document.querySelectorAll(
                    'button,[role="button"],[role="tab"],select,option,a[rel="next"]'
                )).slice(0,300);
                const label = el => String(el.getAttribute('aria-label') ||
                    el.textContent || '').slice(0,100);
                let mask = 0;
                if (items.some(el => /(下書き|公開中|公開済み)/.test(label(el)))) mask |= 1;
                if (items.some(el => /(もっと見る|さらに表示|more|load more)/i.test(label(el)))) mask |= 2;
                if (items.some(el => el.tagName === 'A' &&
                    (el.getAttribute('rel') || '').includes('next') ||
                    /(次へ|next)/i.test(label(el)) && el.tagName === 'A')) mask |= 4;
                if (items.some(el => /(下書き)/.test(label(el)) &&
                    (el.getAttribute('aria-selected') === 'true' ||
                     el.getAttribute('aria-pressed') === 'true'))) mask |= 8;
                // Structural-only, allowlisted evidence. No page text, DOM,
                // private identifiers, URLs or element counts leave the VM.
                const root = document.scrollingElement || document.documentElement;
                if (root && root.scrollHeight > root.clientHeight + 8) mask |= 16;
                const main = document.querySelector('main,[role="main"]');
                if (main && main.children.length > 0) mask |= 64;
                const descendants = main ?
                    Array.from(main.querySelectorAll('*')).slice(0,300) : [];
                if (descendants.some(el => {
                    const overflow = getComputedStyle(el).overflowY;
                    return (overflow === 'auto' || overflow === 'scroll') &&
                        el.scrollHeight > el.clientHeight + 8;
                })) mask |= 32;
                if (items.some(el => el.tagName === 'BUTTON' &&
                    /を編集/.test(label(el)))) mask |= 128;
                if (document.querySelector('[aria-busy="true"],[role="progressbar"]'))
                    mask |= 256;
                if (root && (getComputedStyle(root).overflowY === 'hidden' ||
                    (document.body && getComputedStyle(document.body).overflowY === 'hidden')))
                    mask |= 512;
                return mask;
            }""")
            if not isinstance(mask, int) or isinstance(mask, bool) or not 0 <= mask < (1 << 10):
                return evidence | {"list_scan_unavailable"}
            for bit, code in (
                (1, "list_draft_filter_visible"), (2, "list_more_control_visible"),
                (4, "list_pagination_visible"), (8, "list_draft_filter_active"),
                (16, "list_root_scrollable"), (32, "list_nested_scrollable"),
                (64, "list_main_populated"), (128, "list_any_edit_control"),
                (256, "list_loading_visible"), (512, "list_scroll_overflow_hidden"),
            ):
                if mask & bit:
                    evidence.add(code)

            for _ in range(4):  # at most twelve scroll operations in total
                if int(page.get_by_role(
                    "button", name=title + "を編集", exact=True
                ).count()) != 0:
                    evidence.add("list_title_found_after_scroll")
                    return evidence
                delta = page.evaluate("""() => {
                    const root = document.scrollingElement || document.documentElement;
                    const before = root.scrollTop;
                    window.scrollBy(0, 1000);
                    return Number(root.scrollTop > before);
                }""")
                evidence.add("list_scroll_attempted")
                if delta not in (0, 1) or isinstance(delta, bool):
                    return evidence | {"list_scan_unavailable"}
                if delta == 0:
                    evidence.add("list_scroll_no_motion")
                page.wait_for_timeout(650)
                if int(page.get_by_role(
                    "button", name=title + "を編集", exact=True
                ).count()) != 0:
                    evidence.add("list_title_found_after_scroll")
                    return evidence

            # Do not invent a page number or click any UI control. Only the
            # explicitly rendered next anchor's href may be visited.
            if page_index == 2:
                break
            raw = page.evaluate(r"""() => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                const item = anchors.find(a => (a.getAttribute('rel') || '')
                    .split(/\s+/).includes('next') ||
                    /(次へ|next)/i.test(
                      (a.getAttribute('aria-label') || a.textContent || '').slice(0,60)));
                return item ? item.getAttribute('href') : '';
            }""")
            if not isinstance(raw, str) or not raw or len(raw) > 400:
                break
            candidate = urljoin("https://note.com/notes", raw)
            parsed = urlsplit(candidate)
            if (parsed.scheme != "https" or parsed.hostname != "note.com"
                or parsed.path != "/notes" or parsed.fragment
                or parsed.username or parsed.password or parsed.port):
                break
            params = parse_qs(parsed.query, keep_blank_values=True)
            if set(params) != {"page"} or len(params["page"]) != 1:
                break
            page_value = params["page"][0]
            if not page_value.isascii() or not page_value.isdecimal() or not 2 <= int(page_value) <= 500:
                break
            if candidate in visited:
                break
            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(650)
            actual = urlsplit(str(page.url or ""))
            if (actual.scheme != "https" or actual.hostname != "note.com"
                or actual.path != "/notes" or
                draft_audit.note_base._looks_logged_out(page)):
                return evidence | {"list_scan_unavailable"}
            visited.add(candidate)
            evidence.add("list_pagination_followed")
    except Exception:
        return evidence | {"list_scan_unavailable"}
    return evidence | {"list_scan_limit_reached"}


_EXACT_READONLY_DRAFT_LIST_URL = "https://note.com/notes?kind=draft"


def _bounded_draft_view_probe(page: Any, title: str) -> set[str]:
    """Inspect one fixed browser draft-view GET after exact account ownership proof.

    /notes?kind=draft is a documented user-facing browser view in a public
    Playwright walkthrough, NOT a documented API. It is provisional until the
    live URL is verified. The probe never clicks, types, mutates, publishes or
    turns a missing title into proof that a private draft does not exist.
    """
    evidence: set[str] = set()
    try:
        page.goto(
            _EXACT_READONLY_DRAFT_LIST_URL,
            wait_until="domcontentloaded", timeout=60000,
        )
        page.wait_for_timeout(1200)
        parsed = urlsplit(str(page.url or ""))
        if (parsed.scheme != "https" or parsed.hostname != "note.com" or
            parsed.path != "/notes" or parsed.query != "kind=draft" or
            parsed.fragment or parsed.username or parsed.password or
            parsed.port is not None or draft_audit.note_base._looks_logged_out(page)):
            return {"list_draft_route_unverified"}
        evidence.add("list_draft_view_open")
    except Exception:
        return {"list_draft_view_unavailable"}

    # Evaluate a bounded, fixed-code DOM bitmask in the private browser.
    # The exact owner-title comparison is local to the VM; no private DOM,
    # article identifiers, links, visible text or element counts leave it.
    try:
        mask = page.evaluate(r"""(targetTitle) => {
            const controls = Array.from(document.querySelectorAll(
                'a,button,[role="tab"],[role="menuitem"],[role="button"]'
            )).slice(0,300);
            const norm = s => String(s || '').replace(/\s+/g,' ').trim();
            const name = el => norm(el.getAttribute('aria-label') ||
                el.textContent || '').slice(0,120);
            const visible = el => {
                const box = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return box.width > 0 && box.height > 0 &&
                    style.visibility !== 'hidden' && style.display !== 'none';
            };
            const owner = controls.filter(el => visible(el) &&
                name(el) === '自分の記事');
            const draft = controls.filter(el => visible(el) &&
                name(el) === '下書き');
            const safeNotesHref = el => {
                try {
                    const raw = el.getAttribute('href');
                    if (!raw) return false;
                    const u = new URL(raw, location.origin);
                    return u.protocol === 'https:' && u.hostname === 'note.com' &&
                        u.port === '' && u.pathname === '/notes' &&
                        (!u.search || u.search === '?kind=draft') &&
                        u.hash === '';
                } catch (_) { return false; }
            };
            let bits = 0;
            if (owner.length) bits |= 1;
            if (draft.length) bits |= 2;
            if (draft.some(el =>
                el.getAttribute('aria-selected') === 'true' ||
                el.getAttribute('aria-current') === 'page' ||
                el.getAttribute('aria-pressed') === 'true')) bits |= 4;
            if (controls.some(el => visible(el) && /を編集/.test(name(el))))
                bits |= 8;
            if (owner.some(el => el.tagName === 'A')) bits |= 16;
            if (owner.some(el => el.tagName === 'BUTTON' ||
                el.getAttribute('role') === 'button')) bits |= 32;
            if (owner.some(el => el.tagName === 'A' && safeNotesHref(el)))
                bits |= 64;
            const target = norm(targetTitle);
            if (controls.some(el => el.tagName === 'A' && visible(el) &&
                name(el) === target)) bits |= 128;
            // Exact, visible, leaf-level text evidence (never export the text).
            const main = document.querySelector('main,[role="main"]');
            const root = main || document.body;
            const textNodes = Array.from(root.querySelectorAll(
                'h1,h2,h3,h4,p,span,div'
            )).slice(0,600);
            if (textNodes.some(el => visible(el) && norm(el.textContent) === target &&
                (!el.children.length || el.children.length <= 1))) bits |= 256;
            if (controls.some(el => el.tagName === 'A' && visible(el) &&
                (() => { try {
                    const u = new URL(el.getAttribute('href') || '', location.origin);
                    return u.protocol === 'https:' &&
                        (u.hostname === 'note.com' ||
                         u.hostname === 'editor.note.com') &&
                        /^\/notes\/n[a-z0-9]+\/edit\/?$/.test(u.pathname);
                } catch (_) { return false; } })())) bits |= 512;
            if (Array.from(root.querySelectorAll('article')).some(visible) ||
                controls.some(el => el.tagName === 'A' && visible(el) &&
                    (() => { try {
                        const u = new URL(el.getAttribute('href') || '', location.origin);
                        return u.protocol === 'https:' &&
                            u.hostname === 'note.com' &&
                            /^\/trendhub_biz\/n\/n[a-z0-9]+\/?$/.test(u.pathname);
                    } catch (_) { return false; } })())) bits |= 1024;
            if (controls.some(el => el.tagName === 'BUTTON' && visible(el) &&
                el.getAttribute('aria-haspopup') === 'menu' &&
                /(プロフィール|アカウント|メニュー)/.test(name(el))))
                bits |= 2048;
            if (main && main.children.length > 0) bits |= 4096;
            const bodyText = norm(root.textContent).slice(0,6000);
            if (/(記事がありません|記事はありません|表示できません|エラーが発生|読み込みに失敗)/.test(bodyText))
                bits |= 8192;
            if (root.querySelector('[aria-busy="true"],[role="progressbar"],[class*="skeleton"]'))
                bits |= 16384;
            if (document.querySelector('iframe')) bits |= 32768;
            return bits;
        }""", title)
        if not isinstance(mask, int) or isinstance(mask, bool) or not 0 <= mask < (1 << 16):
            evidence.add("list_draft_structure_unavailable")
        else:
            for bit, code in (
                (1, "list_self_articles_nav_visible"),
                (2, "list_draft_filter_nav_visible"),
                (4, "list_draft_filter_selected"),
                (8, "list_draft_any_edit_control"),
                (16, "list_owner_nav_anchor"),
                (32, "list_owner_nav_button"),
                (64, "list_owner_nav_note_href"),
                (128, "list_title_exact_anchor"),
                (256, "list_title_exact_plain_text"),
                (512, "list_existing_edit_href"),
                (1024, "list_article_card_present"),
                (2048, "list_profile_menu_trigger"),
                (4096, "list_main_content_populated"),
                (8192, "list_empty_or_error_notice"),
                (16384, "list_loading_placeholder"),
                (32768, "list_embedded_frame"),
            ):
                if mask & bit:
                    evidence.add(code)
    except Exception:
        evidence.add("list_draft_structure_unavailable")

    try:
        count = int(page.get_by_role(
            "button", name=title + "を編集", exact=True
        ).count())
    except Exception:
        return evidence | {"list_draft_structure_unavailable"}
    if count == 1:
        evidence.add("list_draft_title_unique")
    elif count > 1:
        evidence.add("list_draft_title_ambiguous")
    else:
        evidence.add("list_draft_title_not_visible")
    return evidence


def _safe_owner_articles_menu_route(page: Any, title: str) -> set[str]:
    """Navigate only an observed "自分の記事" link on verified owner settings.

    The sole optional click opens a uniquely identified *profile menu* button
    with aria-haspopup=menu. It never clicks an article, save/publish control,
    arbitrary URL or an unevidenced navigation. The link must be a visible
    exact accessible link to one of two known HTTPS note.com article-list
    browser routes. All DOM/text stays on the private VM.
    """
    try:
        settings = urlsplit(str(page.url or ""))
        expected = urlsplit(cloud.PROFILE_SETTINGS_URL)
        if (settings.scheme != expected.scheme or
            settings.hostname != expected.hostname or
            settings.path != expected.path or settings.query or
            settings.fragment or settings.username or settings.password or
            settings.port is not None):
            return {"menu_origin_unverified"}
    except Exception:
        return {"menu_origin_unverified"}

    evidence: set[str] = set()

    def exact_link() -> tuple[str, Any | None]:
        try:
            item = page.get_by_role("link", name="自分の記事", exact=True)
            count = int(item.count())
            if count > 1:
                return ("ambiguous", None)
            if count == 1 and item.is_visible():
                return ("found", item)
            return ("missing", None)
        except Exception:
            return ("uninspectable", None)

    status, link = exact_link()
    if status == "ambiguous":
        return {"menu_link_ambiguous"}
    if status == "uninspectable":
        return {"menu_link_uninspectable"}
    if status == "missing":
        try:
            candidates = page.locator('button[aria-haspopup="menu"]:visible')
            count = min(int(candidates.count()), 25)
            semantic = []
            for index in range(count):
                trigger = candidates.nth(index)
                label = str(trigger.get_attribute("aria-label") or "").strip()
                if label in {
                    "プロフィール", "プロフィールメニュー",
                    "アカウント", "アカウントメニュー",
                } and trigger.is_visible():
                    semantic.append(trigger)
        except Exception:
            return {"menu_trigger_missing", "menu_link_missing"}
        if len(semantic) != 1:
            return {
                "menu_trigger_ambiguous" if semantic else "menu_trigger_missing",
                "menu_link_missing",
            }
        evidence.add("menu_trigger_unique")
        try:
            semantic[0].click(timeout=3000)
            page.wait_for_timeout(350)
            if urlsplit(str(page.url or "")) != settings:
                return evidence | {"menu_open_failed"}
        except Exception:
            return evidence | {"menu_open_failed"}
        evidence.add("menu_opened")
        status, link = exact_link()
        if status == "ambiguous":
            return evidence | {"menu_link_ambiguous"}
        if status == "uninspectable":
            return evidence | {"menu_link_uninspectable"}
        if status == "missing":
            return evidence | {"menu_link_missing"}

    try:
        raw = str(link.get_attribute("href") or "")
        dest = urlsplit(urljoin("https://note.com", raw))
        if (dest.scheme != "https" or dest.hostname != "note.com" or
            dest.username or dest.password or dest.port is not None or
            dest.path != "/notes" or
            dest.query not in ("", "kind=draft") or dest.fragment):
            return evidence | {"menu_link_rejected"}
        url = dest.geturl()
    except Exception:
        return evidence | {"menu_link_rejected"}
    evidence.add("menu_link_exact")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1200)
        actual = urlsplit(str(page.url or ""))
        if (actual != dest or draft_audit.note_base._looks_logged_out(page)):
            return evidence | {"menu_route_unverified"}
        evidence.add("menu_route_open")
    except Exception:
        return evidence | {"menu_route_unavailable"}

    # Bounded DOM signature, comparable to the direct-list fixed-code probe.
    try:
        mask = page.evaluate(r"""(targetTitle) => {
            const visible = el => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                    s.visibility !== 'hidden' && s.display !== 'none';
            };
            const norm = x => String(x || '').replace(/\s+/g, ' ').trim();
            const root = document.querySelector('main,[role="main"]');
            const main = root || document.body;
            const actions = Array.from(document.querySelectorAll(
                'a[href],button,[role="button"],[role="tab"]'
            )).slice(0,300).filter(visible);
            let bits = 0;
            if (root && root.children.length) bits |= 1;
            if (Array.from(main.querySelectorAll('article')).slice(0,100)
                    .some(visible)) bits |= 2;
            if (actions.some(el => /を編集/.test(norm(
                el.getAttribute('aria-label') || el.textContent)))) bits |= 4;
            if (actions.some(el => norm(el.textContent) === norm(targetTitle)))
                bits |= 8;
            if (actions.some(el => norm(el.textContent) === '下書き'))
                bits |= 16;
            if (main.querySelector('[aria-busy="true"],[role="progressbar"],[class*="skeleton"]'))
                bits |= 32;
            return bits;
        }""", title)
        if isinstance(mask, int) and not isinstance(mask, bool) and 0 <= mask < 64:
            for bit, code in (
                (1, "menu_route_main_populated"),
                (2, "menu_route_article_card_present"),
                (4, "menu_route_edit_control_present"),
                (8, "menu_route_title_visible"),
                (16, "menu_route_draft_filter_visible"),
                (32, "menu_route_loading"),
            ):
                if mask & bit:
                    evidence.add(code)
    except Exception:
        pass
    return evidence


_EXACT_READONLY_NOTE_HOME_URL = "https://note.com/"


def _safe_note_home_svg_context_probe(page: Any) -> set[str]:
    """Classify visible SVG-button context on verified note home, no interaction.

    A generic SVG is *not* evidence of a profile trigger. This is a diagnostic
    only and never authorizes article recovery, navigation, menu clicks or
    creation. Only a fixed 14-bit mask leaves the private page; no labels,
    element text, raw DOM, URLs, IDs or numerical counts are returned.
    """
    if (str(getattr(page, "url", "") or "") != _EXACT_READONLY_NOTE_HOME_URL or
        draft_audit.note_base._looks_logged_out(page)):
        return {"home_svg_context_uninspectable"}
    try:
        mask = page.evaluate(r"""() => {
            // SVG_CONTEXT_FIXED_BITS: never export private DOM or attributes.
            const header = document.querySelector('header,[role="banner"]');
            const vis = el => {
                const b = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return b.width > 0 && b.height > 0 &&
                    s.visibility !== 'hidden' && s.display !== 'none';
            };
            const all = Array.from(document.querySelectorAll(
                'button,[role="button"]'
            )).slice(0,250).filter(vis);
            const svgButtons = all.filter(el => el.querySelector('svg'));
            const headerButtons = svgButtons.filter(el =>
                header && header.contains(el));
            const accessible = el => String(
                el.getAttribute('aria-label') ||
                el.getAttribute('title') ||
                el.getAttribute('data-tooltip') ||
                el.querySelector('svg title')?.textContent || ''
            ).replace(/\s+/g,' ').trim().slice(0,100);
            const isNamed = (el, pattern) => pattern.test(accessible(el));
            const profile = /^(プロフィール|アカウント|マイページ|ユーザーメニュー|プロフィールメニュー|profile|account|user menu|my account)$/i;
            const search = /^(検索|検索する|search|search notes)$/i;
            const alerts = /^(通知|お知らせ|notifications?|alerts?)$/i;
            const compose = /^(投稿|記事を書く|書く|新規投稿|create|write|post)$/i;
            const visibleControls = Array.from(document.querySelectorAll(
                'a,button,[role="link"],[role="button"]'
            )).slice(0,350).filter(vis);
            const ownProfile = el => {
                try {
                    const href = el.getAttribute('href');
                    if (!href) return false;
                    const u = new URL(href,location.origin);
                    return u.protocol === 'https:' && u.hostname === 'note.com' &&
                        u.port === '' && u.pathname === '/trendhub_biz' &&
                        !u.search && !u.hash;
                } catch (_) { return false; }
            };
            const label = el => String(el.getAttribute('aria-label') ||
                el.textContent || '').replace(/\s+/g,' ').trim().slice(0,80);
            let bits = 0;
            if (headerButtons.length === 1) bits |= 1;
            if (headerButtons.length > 1) bits |= 2;
            if (svgButtons.some(el => !header || !header.contains(el))) bits |= 4;
            if (headerButtons.some(el => isNamed(el,profile))) bits |= 8;
            if (headerButtons.some(el => isNamed(el,search))) bits |= 16;
            if (headerButtons.some(el => isNamed(el,alerts))) bits |= 32;
            if (headerButtons.some(el => isNamed(el,compose))) bits |= 64;
            if (headerButtons.some(el => ['menu','true'].includes(
                el.getAttribute('aria-haspopup')))) bits |= 128;
            if (headerButtons.some(el => !accessible(el))) bits |= 256;
            if (headerButtons.some(el => el.querySelector('img'))) bits |= 512;
            if (visibleControls.some(el =>
                /^(ログイン|ログインする|sign in|log in)$/i.test(label(el)))) bits |= 1024;
            if (visibleControls.some(el =>
                /^(新規登録|会員登録|アカウント登録|sign up|register)$/i.test(label(el)))) bits |= 2048;
            if (header && Array.from(header.querySelectorAll('a[href]')).slice(0,80)
                    .some(el => vis(el) && !!el.querySelector('svg'))) bits |= 4096;
            if (header && Array.from(header.querySelectorAll('a[href]')).slice(0,80)
                    .some(el => vis(el) && ownProfile(el))) bits |= 8192;
            return bits;
        }""")
        if (not isinstance(mask, int) or isinstance(mask, bool) or
            not 0 <= mask < (1 << 14)):
            return {"home_svg_context_uninspectable"}
        return {
            code for bit, code in (
                (1, "home_svg_header_unique"),
                (2, "home_svg_header_multiple"),
                (4, "home_svg_outside_header"),
                (8, "home_svg_header_account_name_hint"),
                (16, "home_svg_header_search_name_hint"),
                (32, "home_svg_header_notification_name_hint"),
                (64, "home_svg_header_compose_name_hint"),
                (128, "home_svg_header_menu_semantics"),
                (256, "home_svg_header_unlabeled"),
                (512, "home_svg_header_image_child"),
                (1024, "home_svg_guest_login_visible"),
                (2048, "home_svg_guest_signup_visible"),
                (4096, "home_svg_header_icon_link_visible"),
                (8192, "home_svg_header_profile_link_visible"),
            ) if mask & bit
        }
    except Exception:
        return {"home_svg_context_uninspectable"}


def _safe_note_home_profile_probe(page: Any) -> set[str]:
    """Inspect the authenticated note homepage, never edit or create anything.

    Official note help directs browser users through the top-right profile
    icon to "自分の記事". The verified settings page is not that entry.
    This bounded probe follows only an exact, visible, uniquely observed
    same-origin article-list link. No menu or article button is clicked.
    Private labels, URLs, HTML and IDs never enter the result.
    """
    evidence: set[str] = set()
    try:
        page.goto(
            _EXACT_READONLY_NOTE_HOME_URL,
            wait_until="domcontentloaded", timeout=60000,
        )
        page.wait_for_timeout(1200)
        parsed = urlsplit(str(page.url or ""))
        if (parsed.scheme != "https" or parsed.hostname != "note.com" or
            parsed.path != "/" or parsed.query or parsed.fragment or
            parsed.username or parsed.password or parsed.port is not None or
            draft_audit.note_base._looks_logged_out(page)):
            return {"home_route_unverified"}
        evidence.add("home_open")
    except Exception:
        return {"home_unavailable"}

    # Every private DOM decision stays in the owner VM; export fixed bits only.
    try:
        home_mask_script = r"""() => {
            const controls = Array.from(document.querySelectorAll(
                'a[href],button,[role="button"],[role="menuitem"],[role="tab"]'
            )).slice(0,400);
            const text = el => String(el.getAttribute('aria-label') ||
                el.textContent || '').replace(/\s+/g,' ').trim().slice(0,90);
            const visible = el => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 &&
                    style.visibility !== 'hidden' && style.display !== 'none';
            };
            const profileHref = el => {
                try {
                    const href = el.getAttribute('href');
                    if (!href) return false;
                    const u = new URL(href, location.origin);
                    return u.protocol === 'https:' &&
                        u.hostname === 'note.com' && u.port === '' &&
                        u.pathname === '/trendhub_biz' && !u.search && !u.hash;
                } catch (_) { return false; }
            };
            const isOwner = el => text(el) === '自分の記事';
            let bits = 0;
            const main = document.querySelector('main,[role="main"]');
            const header = document.querySelector('header,[role="banner"]');
            if (main && main.children.length > 0) bits |= 1;
            if (controls.some(el => el.tagName === 'A' &&
                visible(el) && profileHref(el))) bits |= 2;
            if (controls.some(el => el.tagName === 'BUTTON' &&
                visible(el) && el.querySelector('img'))) bits |= 4;
            if (controls.some(el => el.tagName === 'BUTTON' && visible(el) &&
                el.getAttribute('aria-haspopup') === 'menu')) bits |= 8;
            if (controls.some(el => el.tagName === 'A' && visible(el) &&
                isOwner(el))) bits |= 16;
            if (controls.some(el => el.tagName === 'A' && !visible(el) &&
                isOwner(el))) bits |= 32;
            if (controls.some(el => el.tagName === 'A' && visible(el) &&
                text(el) === '下書き')) bits |= 64;
            if (main && Array.from(main.querySelectorAll('article')).slice(0,100)
                .some(visible)) bits |= 128;
            if (document.querySelector(
                '[aria-busy="true"],[role="progressbar"],[class*="skeleton"]'
            )) bits |= 256;
            if (controls.some(el => visible(el) &&
                /^(プロフィール|アカウント|マイページ|メニュー)$/.test(text(el))))
                bits |= 512;
            if (header && visible(header)) bits |= 1024;
            if (header && Array.from(header.querySelectorAll('img')).slice(0,50)
                .some(visible)) bits |= 2048;
            if (controls.some(el => el.tagName === 'BUTTON' && visible(el) &&
                el.querySelector('svg'))) bits |= 4096;
            if (controls.some(el => el.tagName === 'BUTTON' && visible(el) &&
                /(投稿|書く)/.test(text(el)) &&
                el.getAttribute('aria-haspopup'))) bits |= 8192;
            return bits;
        }"""
        mask = page.evaluate(home_mask_script)
        # The home page is often still hydrating after DOMContentLoaded.
        # Only re-read a fixed-bit DOM signature while a loading placeholder
        # persists and no account/navigation controls have appeared. At most
        # eight 1.2-second waits; never click or follow an unobserved route.
        for _ in range(8):
            if (not isinstance(mask, int) or isinstance(mask, bool) or
                not 0 <= mask < (1 << 14)):
                break
            if not (mask & 256) or (mask & (2 | 4 | 8 | 16 | 32 | 512 | 2048 | 4096)):
                break
            page.wait_for_timeout(1200)
            refreshed_url = urlsplit(str(page.url or ""))
            if (refreshed_url.scheme != "https" or
                refreshed_url.hostname != "note.com" or
                refreshed_url.path != "/" or refreshed_url.query or
                refreshed_url.fragment or refreshed_url.username or
                refreshed_url.password or refreshed_url.port is not None or
                draft_audit.note_base._looks_logged_out(page)):
                return evidence | {"home_route_unverified"}
            mask = page.evaluate(home_mask_script)
        if not isinstance(mask, int) or isinstance(mask, bool) or not 0 <= mask < (1 << 14):
            evidence.add("home_dom_uninspectable")
        else:
            for bit, code in (
                (1, "home_main_populated"),
                (2, "home_creator_profile_link_visible"),
                (4, "home_avatar_button_visible"),
                (8, "home_profile_menu_trigger_visible"),
                (16, "home_owner_article_link_visible"),
                (32, "home_owner_article_link_hidden"),
                (64, "home_draft_link_visible"),
                (128, "home_article_card_visible"),
                (256, "home_loading_visible"),
                (512, "home_profile_label_visible"),
                (1024, "home_header_visible"),
                (2048, "home_avatar_image_visible"),
                (4096, "home_avatar_svg_button_visible"),
                (8192, "home_post_dropdown_visible"),
            ):
                if mask & bit:
                    evidence.add(code)
    except Exception:
        evidence.add("home_dom_uninspectable")

    # A generic SVG button does not prove an account menu. Observe only
    # the fixed-code structural context, without clicking or exporting DOM.
    if ("home_avatar_svg_button_visible" in evidence and
        "home_owner_article_link_visible" not in evidence and
        "home_loading_visible" not in evidence):
        evidence.update(_safe_note_home_svg_context_probe(page))

    try:
        link = page.get_by_role("link", name="自分の記事", exact=True)
        count = int(link.count())
        if count > 1:
            return evidence | {"home_owner_link_ambiguous"}
        if count != 1 or not link.is_visible():
            return evidence | {"home_owner_link_missing"}
        raw = str(link.get_attribute("href") or "")
    except Exception:
        return evidence | {"home_owner_link_uninspectable"}
    try:
        dest = urlsplit(urljoin(_EXACT_READONLY_NOTE_HOME_URL, raw))
        if (dest.scheme != "https" or dest.hostname != "note.com" or
            dest.username or dest.password or dest.port is not None or
            dest.path != "/notes" or
            dest.query not in ("", "kind=draft") or dest.fragment):
            return evidence | {"home_owner_link_rejected"}
    except Exception:
        return evidence | {"home_owner_link_rejected"}
    evidence.add("home_owner_link_exact")

    # A fixed HTTPS GET of an observed navigation link, never an article URL.
    try:
        page.goto(dest.geturl(), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1200)
        if urlsplit(str(page.url or "")) != dest or draft_audit.note_base._looks_logged_out(page):
            return evidence | {"home_owner_route_unverified"}
        evidence.add("home_owner_route_open")
    except Exception:
        return evidence | {"home_owner_route_unavailable"}

    try:
        mask = page.evaluate(r"""() => {
            const root = document.querySelector('main,[role="main"]');
            const main = root || document.body;
            const visible = el => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 &&
                    s.visibility !== 'hidden' && s.display !== 'none';
            };
            let bits = 0;
            if (root && root.children.length) bits |= 1;
            if (Array.from(main.querySelectorAll('article')).slice(0,100)
                    .some(visible)) bits |= 2;
            if (Array.from(main.querySelectorAll(
                'a,button,[role="button"]'
            )).slice(0,300).some(el => visible(el) &&
                /を編集/.test(String(el.getAttribute('aria-label') ||
                    el.textContent || '')))) bits |= 4;
            return bits;
        }""")
        if isinstance(mask, int) and not isinstance(mask, bool) and 0 <= mask < 8:
            for bit, code in (
                (1, "home_owner_route_main_populated"),
                (2, "home_owner_route_article_card_present"),
                (4, "home_owner_route_edit_control_present"),
            ):
                if mask & bit:
                    evidence.add(code)
    except Exception:
        pass
    return evidence


def _probe_official_article_list(
    context: Any,
    article: dict[str, Any],
    record: DeliveryRecord,
    history_candidates: list[str],
) -> set[str]:
    """Read the authenticated official note list without changing draft content.

    Read-only account settings proof is required before inspecting note.com/notes.
    Only an exact unique existing-title edit button may be clicked for navigation
    to an existing article. No list-only evidence can authorize recovery:
    private/draft lifecycle is not proven by an edit control or matching content.
    No private URLs, title text, body, IDs, or exceptions leave this probe.
    """
    codes: set[str] = set()
    page = None
    try:
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            cloud._assert_expected_note_account(page)
        except Exception:
            return {"account_unverified"}
        codes.add("account_proven")
        # Compare owner-menu navigation with the already-established direct
        # list/draft-view probes. Only try this when the account ownership
        # proof left us on the exact expected settings page.
        if str(getattr(page, "url", "") or "") == cloud.PROFILE_SETTINGS_URL:
            codes.update(_safe_owner_articles_menu_route(
                page, str(article["title"]).strip()
            ))
            # Owner-authenticated homepage is the documented entry for the
            # top-right profile icon. Inspect it without any button click.
            codes.update(_safe_note_home_profile_probe(page))

        # Passive API observation after verified account ownership, while the
        # ordinary official list loads. Never request a guessed/private endpoint.
        api_seen = [0]
        def on_api_response(response: Any) -> None:
            try:
                # Never decode additional private API response bodies after cap.
                if api_seen[0] >= _MAX_NOTE_API_RESPONSES:
                    codes.add("api_capture_limit")
                    return
                signals = _safe_note_api_response_signals(
                    response, str(article["title"]).strip()
                )
                if not signals:
                    return
                api_seen[0] += 1
                codes.update(signals)
            except Exception:
                # No browser exception text, response body, URL or ID escapes.
                return

        try:
            page.on("response", on_api_response)
        except Exception:
            # Legacy fake-page tests have no event listener. In live Playwright
            # this is passive and optional, never recovery authority.
            pass

        try:
            page.goto(cloud.ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            parsed = urlparse(str(page.url or ""))
            if (parsed.scheme != "https" or (parsed.hostname or "").lower() != "note.com"
                or parsed.path != "/notes" or draft_audit.note_base._looks_logged_out(page)):
                return codes | {"list_unavailable"}
        except Exception:
            return codes | {"list_unavailable"}
        codes.add("list_open")

        try:
            button = page.get_by_role(
                "button", name=str(article["title"]).strip() + "を編集", exact=True
            )
            count = int(button.count())
        except Exception:
            return codes | {"title_button_uninspectable"}
        if count == 0:
            scan = _bounded_official_list_scan(page, str(article["title"]).strip())
            codes.update(scan)
            try:
                button = page.get_by_role(
                    "button", name=str(article["title"]).strip() + "を編集", exact=True
                )
                count = int(button.count())
            except Exception:
                return codes | {"title_button_uninspectable"}
            if count == 0:
                # Owner-only: inspect exactly one read-only browser draft view.
                # No API endpoint or article edit route is inferred or clicked.
                draft_codes = _bounded_draft_view_probe(
                    page, str(article["title"]).strip()
                )
                codes.update(draft_codes)
                if "list_draft_view_open" not in draft_codes:
                    return codes | {"title_button_not_visible"}
                try:
                    button = page.get_by_role(
                        "button", name=str(article["title"]).strip() + "を編集",
                        exact=True,
                    )
                    count = int(button.count())
                except Exception:
                    return codes | {"title_button_uninspectable"}
                if count == 0:
                    return codes | {"title_button_not_visible"}
        if count != 1:
            return codes | {"title_button_ambiguous"}
        codes.add("title_button_unique")

        # NEVER click a button in a CREATION_UNKNOWN recovery. Only an
        # explicitly linked pre-existing edit route may be navigated to.
        try:
            raw_href = button.evaluate("""el => {
                const anchor = el.closest('a[href]') || el.querySelector('a[href]');
                return anchor ? anchor.getAttribute('href') : '';
            }""")
            if not isinstance(raw_href, str) or not raw_href:
                return codes | {"editor_route_unverified"}
            direct_url = urljoin("https://note.com", raw_href)
            linked_id = reconcile.draft_identity_from_url(direct_url)
        except Exception:
            return codes | {"editor_route_unverified"}
        try:
            page.goto(direct_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
        except Exception:
            return codes | {"edit_navigation_failed"}
        try:
            if not editor_readiness._is_editor_url(str(page.url or "")):
                return codes | {"editor_route_unverified"}
            identity = reconcile.draft_identity_from_url(str(page.url or ""))
            if identity != linked_id:
                return codes | {"editor_route_unverified"}
        except Exception:
            return codes | {"editor_route_unverified"}
        codes.add("editor_route_verified")

        known_ids = set()
        for url in history_candidates:
            try:
                known_ids.add(reconcile.draft_identity_from_url(url))
            except Exception:
                pass
        codes.add("editor_in_history" if identity in known_ids else "editor_not_in_history")

        try:
            title = draft_audit._title_value(page)
        except Exception:
            return codes | {"editor_title_unreadable"}
        if title != str(article["title"]).strip():
            return codes | {"editor_title_mismatch"}
        codes.add("editor_title_equal")

        try:
            draft_audit._audit_current_page(
                page, str(article["title"]), str(article["manuscript"])
            )
        except Exception:
            return codes | {"body_eyecatch_unverified"}
        codes.add("body_eyecatch_equal")

        try:
            actual_hash = _current_canonical_sha256(page)
        except Exception:
            return codes | {"canonical_unverified"}
        if actual_hash != record.snapshot.canonical_document_sha256:
            return codes | {"canonical_mismatch"}
        codes.add("canonical_equal")
        return codes
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass


def _discover_verified_matches(
    article: dict[str, Any],
    record: DeliveryRecord,
 ) -> tuple[list[dict[str, Any]], int, dict[str, int], dict[str, int], dict[str, int], dict[str, int], dict[str, int], dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    """Inspect authenticated article list and history without disclosing private IDs."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CreationRecoveryAuditError("Playwright is required for read-only recovery") from exc

    candidates = cloud._recent_private_edit_urls(cloud._profile_dir())
    counts = {bucket: 0 for bucket in REJECTION_BUCKETS}
    stages = {stage: 0 for stage in INSPECTION_STAGES}
    title_failures = {code: 0 for code in TITLE_FAILURE_CODES}
    title_dom_signals = {code: 0 for code in TITLE_DOM_SIGNAL_CODES}
    title_context_signals = {code: 0 for code in TITLE_CONTEXT_CODES}
    title_route_shapes = {code: 0 for code in TITLE_ROUTE_SHAPES}
    title_atomic_dom = {code: 0 for code in TITLE_ATOMIC_DOM_CODES}
    failed_screen_signal_counts = {code: 0 for code in SCREEN_SIGNAL_CODES}
    control_screen_signal_counts = {code: 0 for code in SCREEN_SIGNAL_CODES}
    official_list_proof_counts = {code: 0 for code in OFFICIAL_LIST_CODES}
    official_list_scan_counts = {code: 0 for code in OFFICIAL_LIST_SCAN_CODES}

    matches: list[dict[str, Any]] = []
    legacy_title_finder = draft_audit.note_base._find_title

    def read_only_title_finder(editor_page: Any) -> Any:
        return _read_only_title_field(editor_page, legacy_title_finder)

    # Use a scoped replacement so _title_value, _audit_current_page and
    # canonical hashing read the same verified editor title field.
    with patch.object(draft_audit.note_base, "_find_title", read_only_title_finder):
        with sync_playwright() as playwright:
            context = cloud._launch_persistent_context(playwright)
            page = context.new_page()
            page.set_default_timeout(30000)
            seeded = False
            try:
                try:
                    official_evidence = _probe_official_article_list(context, article, record, candidates)
                except Exception:
                    official_evidence = {"account_unverified"}
                for signal in official_evidence:
                    if signal in OFFICIAL_LIST_SCAN_CODES:
                        official_list_scan_counts[signal] += 1
                    elif signal in OFFICIAL_LIST_CODES:
                        official_list_proof_counts[signal] += 1
                for candidate in candidates:
                    stage = "navigation"
                    response = None
                    try:
                        response = page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(1200)
                        stage = "login_check"
                        if draft_audit.note_base._looks_logged_out(page) and not seeded:
                            seeded = bool(cloud._seed_note_state(context, page))
                            if seeded:
                                response = page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                                page.wait_for_timeout(1200)
                        if draft_audit.note_base._looks_logged_out(page):
                            counts["logged_out"] += 1
                            continue
                        stage = "editor_route"
                        if not editor_readiness._is_editor_url(str(page.url or "")):
                            counts["non_editor"] += 1
                            continue
                        stage = "title_read"
                        if draft_audit._title_value(page) != str(article["title"]).strip():
                            counts["different_title"] += 1
                            for signal in _safe_visible_screen_signals(page):
                                control_screen_signal_counts[signal] += 1
                            continue
                        stage = "body_audit"
                        try:
                            draft_audit._audit_current_page(
                                page,
                                str(article["title"]),
                                str(article["manuscript"]),
                            )
                        except draft_audit.PrivateDraftAuditError:
                            counts["content_or_eyecatch"] += 1
                            continue
                        stage = "canonical_read"
                        if _current_canonical_sha256(page) != record.snapshot.canonical_document_sha256:
                            counts["canonical_hash"] += 1
                            continue

                        stage = "identity_read"
                        verified_editor_url = str(page.url or "").strip()
                        draft_id = reconcile.draft_identity_from_url(
                            verified_editor_url,
                            error_type=CreationRecoveryAuditError,
                        )
                        matches.append(
                            {
                                "draft_id": draft_id,
                                "editor_route_hash": hashlib.sha256(
                                    verified_editor_url.encode("utf-8")
                                ).hexdigest()[:12],
                            }
                        )
                    except CreationRecoveryAuditError:
                        raise
                    except Exception as exc:
                        counts["inspection_error"] += 1
                        stages[stage if stage in stages else "other"] += 1
                        if stage == "title_read":
                            title_failures[_title_failure_code(exc)] += 1
                            if (
                                isinstance(exc, TitleReadInspectionError)
                                and exc.code == "title_selector_unavailable"
                            ):
                                for signal in _safe_title_dom_signals(page):
                                    title_dom_signals[signal] += 1
                                for signal in _safe_title_context_signals(page, candidate, response):
                                    title_context_signals[signal] += 1
                                title_route_shapes[_safe_title_route_shape(str(page.url or ""))] += 1
                                for signal in _safe_title_atomic_dom_signals(page):
                                    title_atomic_dom[signal] += 1
                                for signal in _safe_visible_screen_signals(page):
                                    failed_screen_signal_counts[signal] += 1
                        continue
            finally:
                context.close()
    return (matches, len(candidates), counts, stages, title_failures,
            title_dom_signals, title_context_signals, title_route_shapes, title_atomic_dom,
            failed_screen_signal_counts, control_screen_signal_counts,
            official_list_proof_counts, official_list_scan_counts)


def run(
    *,
    confirm: str,
    sync_id: str,
    note_target: str,
    ledger_path: str,
    prepare_only: bool = False,
) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise CreationRecoveryAuditError(f"Confirmation must equal {CONFIRM_TOKEN}")
    normalized_sync = str(sync_id or "").strip().lower()
    normalized_target = str(note_target or "").strip()
    if len(normalized_sync) != 32 or not normalized_target:
        raise CreationRecoveryAuditError("exact private recovery identity is required")

    ledger = SQLiteDeliveryLedger(Path(ledger_path).expanduser())
    record = require_creation_unknown_record(
        ledger,
        sync_id=normalized_sync,
        note_target=normalized_target,
    )
    prepared = _expected_prepared_delivery(record)
    article = dict(prepared.article)

    base_result: dict[str, Any] = {
        "status": "recovery_ready" if prepare_only else "recovery_not_run",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "match_count": 0,
        "history_candidate_count": 0,
        "editor_route_hash": "",
        "rejection_counts": {bucket: 0 for bucket in REJECTION_BUCKETS},
        "inspection_stage_counts": {stage: 0 for stage in INSPECTION_STAGES},
        "title_failure_counts": {code: 0 for code in TITLE_FAILURE_CODES},
        "title_dom_signal_counts": {code: 0 for code in TITLE_DOM_SIGNAL_CODES},
        "title_context_signal_counts": {code: 0 for code in TITLE_CONTEXT_CODES},
        "title_route_shape_counts": {code: 0 for code in TITLE_ROUTE_SHAPES},
        "title_atomic_dom_counts": {code: 0 for code in TITLE_ATOMIC_DOM_CODES},
        "failed_screen_signal_counts": {code: 0 for code in SCREEN_SIGNAL_CODES},
        "control_screen_signal_counts": {code: 0 for code in SCREEN_SIGNAL_CODES},
        "official_list_proof_counts": {code: 0 for code in OFFICIAL_LIST_CODES},
        "official_list_scan_counts": {code: 0 for code in OFFICIAL_LIST_SCAN_CODES},
    }
    if prepare_only:
        return base_result

    (
        matches, candidate_count, rejection_counts, inspection_stage_counts,
        title_failure_counts, title_dom_signal_counts, title_context_signal_counts,
        title_route_shape_counts, title_atomic_dom_counts,
        failed_screen_signal_counts, control_screen_signal_counts,
        official_list_proof_counts, official_list_scan_counts,
    ) = _discover_verified_matches(article, record)
    base_result["history_candidate_count"] = candidate_count
    base_result["match_count"] = len(matches)
    base_result["rejection_counts"] = {
        bucket: int(rejection_counts.get(bucket, 0)) for bucket in REJECTION_BUCKETS
    }
    base_result["inspection_stage_counts"] = {
        stage: int(inspection_stage_counts.get(stage, 0)) for stage in INSPECTION_STAGES
    }
    base_result["title_failure_counts"] = {
        code: int(title_failure_counts.get(code, 0)) for code in TITLE_FAILURE_CODES
    }
    base_result["title_dom_signal_counts"] = {
        code: int(title_dom_signal_counts.get(code, 0)) for code in TITLE_DOM_SIGNAL_CODES
    }
    base_result["title_context_signal_counts"] = {
        code: int(title_context_signal_counts.get(code, 0)) for code in TITLE_CONTEXT_CODES
    }
    base_result["title_route_shape_counts"] = {
        code: int(title_route_shape_counts.get(code, 0)) for code in TITLE_ROUTE_SHAPES
    }
    base_result["title_atomic_dom_counts"] = {
        code: int(title_atomic_dom_counts.get(code, 0)) for code in TITLE_ATOMIC_DOM_CODES
    }
    base_result["failed_screen_signal_counts"] = {
        code: int(failed_screen_signal_counts.get(code, 0)) for code in SCREEN_SIGNAL_CODES
    }
    base_result["control_screen_signal_counts"] = {
        code: int(control_screen_signal_counts.get(code, 0)) for code in SCREEN_SIGNAL_CODES
    }
    base_result["official_list_proof_counts"] = {
        code: int(official_list_proof_counts.get(code, 0)) for code in OFFICIAL_LIST_CODES
    }
    base_result["official_list_scan_counts"] = {
        code: int(official_list_scan_counts.get(code, 0)) for code in OFFICIAL_LIST_SCAN_CODES
    }
    # Preserve the exact safe counts even on an ambiguous/missing match.
    # Never grant recovery authority or infer permission to create a new draft.
    if len(matches) != 1:
        base_result["status"] = (
            "recovery_no_verified_match" if not matches else "recovery_multiple_verified_matches"
        )
        return base_result
    match = require_unique_recovery_match(matches)
    base_result.update(
        {
            "status": "recovery_candidate_found",
            "editor_route_hash": str(match.get("editor_route_hash") or ""),
            "recovered_draft_id": str(match.get("draft_id") or ""),
        }
    )
    return base_result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", default=os.environ.get("NOTE_RECOVERY_CONFIRM", ""))
    parser.add_argument("--sync-id", default=os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    parser.add_argument("--note-target", default=os.environ.get("NOTE_TARGET_IDENTITY", ""))
    parser.add_argument(
        "--ledger-path",
        default=os.environ.get("NOTE_DELIVERY_LEDGER_PATH", "~/.aiif-note/delivery-ledger-v1.sqlite3"),
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        default=os.environ.get("NOTE_RECOVERY_PREPARE_ONLY", "false").strip().lower()
        in {"1", "true", "yes", "on"},
    )
    parser.add_argument("--result-file", default=os.environ.get("NOTE_RECOVERY_RESULT_FILE", ""))
    args = parser.parse_args()
    result = run(
        confirm=args.confirm,
        sync_id=args.sync_id,
        note_target=args.note_target,
        ledger_path=args.ledger_path,
        prepare_only=args.prepare_only,
    )
    if args.result_file:
        target = Path(args.result_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(safe_recovery_projection(result), ensure_ascii=False))
    # Save sanitized diagnostics before failing closed; the workflow summary then
    # distinguishes zero/multiple matches without exposing a private draft ID.
    if result.get("status") in {
        "recovery_no_verified_match", "recovery_multiple_verified_matches"
    }:
        raise CreationRecoveryAuditError("private draft recovery remains blocked: no unique verified match")


if __name__ == "__main__":
    main()
