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


def _discover_verified_matches(
    article: dict[str, Any],
    record: DeliveryRecord,
) -> tuple[list[dict[str, Any]], int, dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    """Inspect history read-only; count only fixed codes, never private identities."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CreationRecoveryAuditError("Playwright is required for read-only recovery") from exc

    candidates = cloud._recent_private_edit_urls(cloud._profile_dir())
    counts = {bucket: 0 for bucket in REJECTION_BUCKETS}
    stages = {stage: 0 for stage in INSPECTION_STAGES}
    title_failures = {code: 0 for code in TITLE_FAILURE_CODES}
    title_dom_signals = {code: 0 for code in TITLE_DOM_SIGNAL_CODES}
    if not candidates:
        return [], 0, counts, stages, title_failures, title_dom_signals

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
                for candidate in candidates:
                    stage = "navigation"
                    try:
                        page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(1200)
                        stage = "login_check"
                        if draft_audit.note_base._looks_logged_out(page) and not seeded:
                            seeded = bool(cloud._seed_note_state(context, page))
                            if seeded:
                                page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
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
                        continue
            finally:
                context.close()
    return matches, len(candidates), counts, stages, title_failures, title_dom_signals


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
    }
    if prepare_only:
        return base_result

    (
        matches, candidate_count, rejection_counts, inspection_stage_counts,
        title_failure_counts, title_dom_signal_counts,
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
