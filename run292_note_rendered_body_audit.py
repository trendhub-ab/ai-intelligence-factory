#!/usr/bin/env python3
"""Run292/293: renderer-faithful, read-only audit for an existing private note draft.

Run291 compared note's rendered body against a coarse Markdown-to-plain-text helper that is
intentionally suitable only for insertion smoke checks. In particular, that helper removes fenced
code content even though the note paste path renders code visibly. Run292 keeps every Run291
read-only/privacy boundary, but derives the expected visible body from the exact safe HTML renderer
used by draft creation.

Run293 preserves the same gates and adds categorical diagnostics for fixed, non-body audit failures.
Only allow-listed codes are emitted; exception text is never copied into the result.

Failure diagnostics contain only booleans, counts, ratios and categorical codes. They never contain
unpublished title/body text, a draft URL, screenshots, browser storage state, or mutation surfaces.
ZERO Gemini/model calls. No draft mutation. No public release.
"""
from __future__ import annotations

import argparse
import json
import os
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import run291_note_private_draft_audit as base


class _VisibleTextParser(HTMLParser):
    _BLOCK_TAGS = {
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote",
        "pre", "code", "ul", "ol", "br", "hr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


class Run292AuditDiagnosticError(base.PrivateDraftAuditError):
    def __init__(self, code: str, metrics: dict[str, Any]) -> None:
        super().__init__(f"Run292 private draft audit failed safely: {code}")
        self.code = str(code)
        self.safe_metrics = dict(metrics)


def _rendered_visible_text(markdown_text: str) -> str:
    """Return visible text from the exact safe HTML renderer used by note draft creation."""
    parser = _VisibleTextParser()
    parser.feed(base.note_base._markdown_to_safe_html(str(markdown_text or "")))
    parser.close()
    return base._normalized_visible(parser.text())


def _common_prefix_len(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def _common_suffix_len(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[-(index + 1)] == right[-(index + 1)]:
        index += 1
    return index


def _safe_diagnostics(actual: str, expected: str, legacy_expected: str, title: str) -> dict[str, Any]:
    prefix = expected[: min(64, len(expected))]
    suffix = expected[-min(64, len(expected)) :] if expected else ""
    ratio = len(actual) / max(1, len(expected))
    common_base = max(1, min(len(actual), len(expected)))
    normalized_title = base._normalized_visible(title)
    source_index = actual.find(base.run222.SOURCE_HEADING)
    cta_positions = [actual.find(label) for label in base.run222.CTA_HEADINGS]
    cta_positions = [pos for pos in cta_positions if pos >= 0]
    cta_index = min(cta_positions) if cta_positions else -1
    renderer_delta = len(expected) - len(legacy_expected)
    return {
        "expectation_mode": "safe_html_renderer",
        "body_visible_chars": len(actual),
        "expected_visible_chars": len(expected),
        "legacy_expected_visible_chars": len(legacy_expected),
        "renderer_delta_chars": renderer_delta,
        "renderer_delta_ratio": round(len(expected) / max(1, len(legacy_expected)), 4),
        "visible_length_ratio": round(ratio, 4),
        "prefix_match": bool(prefix and prefix in actual),
        "suffix_match": bool(suffix and suffix in actual),
        "exact_visible_match": actual == expected,
        "expected_contained_in_actual": bool(expected and expected in actual),
        "actual_contained_in_expected": bool(actual and actual in expected),
        "common_prefix_ratio": round(_common_prefix_len(actual, expected) / common_base, 4),
        "common_suffix_ratio": round(_common_suffix_len(actual, expected) / common_base, 4),
        "sources_present": source_index >= 0,
        "cta_present": cta_index >= 0,
        "sources_before_cta": source_index >= 0 and cta_index >= 0 and source_index < cta_index,
        "duplicate_title_prefix": bool(normalized_title and actual.startswith(normalized_title)),
    }


def _body_text_metrics(actual_text: str, expected_markdown: str, title: str) -> dict[str, Any]:
    actual = base._normalized_visible(actual_text)
    expected = _rendered_visible_text(expected_markdown)
    legacy_expected = base._normalized_visible(base.note_base._plain_manuscript_text(expected_markdown))
    metrics = _safe_diagnostics(actual, expected, legacy_expected, title)
    metrics["code_fence_marker_count"] = str(expected_markdown or "").count("```")

    if not expected or not actual:
        raise Run292AuditDiagnosticError("empty_body", metrics)
    if not metrics["prefix_match"] or not metrics["suffix_match"]:
        raise Run292AuditDiagnosticError("presentation_boundary_mismatch", metrics)
    if not 0.82 <= float(metrics["visible_length_ratio"]) <= 1.30:
        raise Run292AuditDiagnosticError("visible_length_ratio_out_of_bounds", metrics)
    if not metrics["sources_before_cta"]:
        raise Run292AuditDiagnosticError("footer_order_mismatch", metrics)
    if metrics["duplicate_title_prefix"]:
        raise Run292AuditDiagnosticError("duplicate_title_prefix", metrics)
    return metrics


def run(*, confirm: str, sync_id: str, prepare_only: bool = False) -> dict[str, Any]:
    original = base._body_text_metrics
    base._body_text_metrics = _body_text_metrics
    try:
        return base.run(confirm=confirm, sync_id=sync_id, prepare_only=prepare_only)
    finally:
        base._body_text_metrics = original


_NON_BODY_GUARD_CODES: dict[str, str] = {
    "Run291 requires an exact 32-hex sync_id": "target_sync_id_invalid",
    "Run291 expected exactly one destination row for the requested sync_id": "destination_row_not_unique",
    "Requested row is not current Ready / 投稿準備中": "destination_state_invalid",
    "Requested row already has public-post evidence; private-draft audit refuses it": "public_evidence_present",
    "Destination row has no title": "destination_title_missing",
    "Content Intelligence source page could not be read": "source_page_read_failed",
    "Content Intelligence source is not an active Ready source": "source_not_active_ready",
    "Source and destination titles do not match": "source_destination_title_mismatch",
    "No byte-valid current Publication Contract manuscript exists": "current_contract_manuscript_missing",
    "Current Ready source has no eyecatch": "current_ready_eyecatch_missing",
    "Prepared note presentation is unexpectedly short": "prepared_presentation_too_short",
    "Could not read the private draft title": "title_read_failed",
    "note authentication is not active": "note_auth_inactive",
    "Matched page is not a confirmed note editor route": "editor_route_invalid",
    "Private draft title does not match the requested article": "draft_title_mismatch",
    "Could not read private draft body": "body_read_failed",
    "Could not inspect private draft semantic structure": "semantic_structure_read_failed",
    "Private draft contains a body-level H1": "body_h1_present",
    "Private draft lost its expected heading structure": "heading_structure_lost",
    "Private draft eyecatch persistence could not be confirmed": "eyecatch_persistence_unconfirmed",
    "Private draft editor geometry is unavailable": "editor_geometry_unavailable",
    "Private draft editor content width is unexpectedly narrow": "editor_width_narrow",
    "Playwright is required for Run291": "playwright_missing",
    "No private note edit route is present in persistent Chrome history": "chrome_history_no_routes",
    "The requested private draft could not be matched safely from local Chrome history": "draft_not_matched_from_history",
}


def _safe_non_body_guard_code(exc: base.PrivateDraftAuditError) -> str:
    """Map only fixed, allow-listed Run291 errors to non-content diagnostic codes."""
    message = str(exc)
    if message == f"Confirmation must equal {base.CONFIRM_TOKEN}":
        return "confirmation_invalid"
    return _NON_BODY_GUARD_CODES.get(message, "non_body_guard_failed")


def _safe_failure_result(sync_id: str, code: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "status": "audit_failed_safe",
        "zero_gemini_calls": True,
        "read_only": True,
        "public_release": False,
        "draft_mutation": False,
        "sync_id": base._normalize_sync_id(sync_id),
        "diagnostic_code": str(code),
    }
    for key, value in (metrics or {}).items():
        if key not in {"title", "manuscript", "draft_url", "actual_text", "expected_text"}:
            result[key] = value
    return result


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
    except Run292AuditDiagnosticError as exc:
        result = _safe_failure_result(args.sync_id, exc.code, exc.safe_metrics)
        exit_code = 2
    except base.PrivateDraftAuditError as exc:
        result = _safe_failure_result(args.sync_id, _safe_non_body_guard_code(exc))
        exit_code = 2

    _write_result(args.result_file, result)
    print(json.dumps(result, ensure_ascii=False))
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
