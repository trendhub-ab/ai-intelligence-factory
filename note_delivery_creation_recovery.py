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

import note_delivery_runtime as delivery_runtime
import note_publication_reconcile as reconcile
import run187_note_editor_readiness as editor_readiness
import run190_note_persistent_cloud as cloud
import run194_note_current_contract as current_contract
import run222_note_presentation_integrity as presentation
import run291_note_private_draft_audit as draft_audit
from note_delivery_ledger import DeliveryRecord, DeliveryState, SQLiteDeliveryLedger


CONFIRM_TOKEN = "AUDIT_CREATION_UNKNOWN"


class CreationRecoveryAuditError(RuntimeError):
    pass


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


def _expected_article(sync_id: str) -> dict[str, Any]:
    """Reconstruct the exact current note-editor presentation without generating new content."""
    current_contract.install()
    presentation.install_note(current_contract.base)
    try:
        article = dict(current_contract.base._prepare_article(sync_id))
    except Exception as exc:
        raise CreationRecoveryAuditError("current publication-contract target is not recoverable") from exc
    if not str(article.get("title") or "").strip() or not str(article.get("manuscript") or "").strip():
        raise CreationRecoveryAuditError("current publication-contract target is incomplete")
    return article


def _discover_verified_matches(article: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Inspect recent existing edit routes read-only and return only fully verified matches."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CreationRecoveryAuditError("Playwright is required for read-only recovery") from exc

    candidates = cloud._recent_private_edit_urls(cloud._profile_dir())
    if not candidates:
        return [], 0

    matches: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        seeded = False
        try:
            for candidate in candidates:
                try:
                    page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1200)
                    if draft_audit.note_base._looks_logged_out(page) and not seeded:
                        seeded = bool(cloud._seed_note_state(context, page))
                        if seeded:
                            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_timeout(1200)
                    if draft_audit.note_base._looks_logged_out(page):
                        continue
                    if not editor_readiness._is_editor_url(str(page.url or "")):
                        continue
                    if draft_audit._title_value(page) != str(article["title"]).strip():
                        continue
                    try:
                        draft_audit._audit_current_page(
                            page,
                            str(article["title"]),
                            str(article["manuscript"]),
                        )
                    except draft_audit.PrivateDraftAuditError:
                        continue
                    draft_id = reconcile.draft_identity_from_url(
                        candidate,
                        error_type=CreationRecoveryAuditError,
                    )
                    matches.append(
                        {
                            "draft_id": draft_id,
                            "editor_route_hash": hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:12],
                        }
                    )
                except CreationRecoveryAuditError:
                    raise
                except Exception:
                    continue
        finally:
            context.close()
    return matches, len(candidates)


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
    require_creation_unknown_record(
        ledger,
        sync_id=normalized_sync,
        note_target=normalized_target,
    )
    article = _expected_article(normalized_sync)

    base_result: dict[str, Any] = {
        "status": "recovery_ready" if prepare_only else "recovery_not_run",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "match_count": 0,
        "history_candidate_count": 0,
        "editor_route_hash": "",
    }
    if prepare_only:
        return base_result

    matches, candidate_count = _discover_verified_matches(article)
    base_result["history_candidate_count"] = candidate_count
    base_result["match_count"] = len(matches)
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


if __name__ == "__main__":
    main()
