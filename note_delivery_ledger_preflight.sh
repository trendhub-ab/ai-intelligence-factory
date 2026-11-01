#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import unicodedata

from note_delivery_ledger import (
    DELIVERY_RECORD_SCHEMA_VERSION,
    DESTINATION_SURFACE,
    LOGICAL_KEY_SCHEMA_VERSION,
    SQLITE_SCHEMA_VERSION,
    DeliveryState,
    LedgerSchemaError,
    LedgerUnavailableError,
)


def normalized(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).strip()


def logical_key_for_identity(sync_id: str, note_target: str) -> str:
    material = {
        "schema_version": LOGICAL_KEY_SCHEMA_VERSION,
        "sync_id": normalized(sync_id).lower(),
        "note_target": normalized(note_target),
        "destination_surface": DESTINATION_SURFACE,
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safe_result(status: str, should_run_delivery: bool) -> dict[str, object]:
    return {
        "status": status,
        "should_run_delivery": bool(should_run_delivery),
        "zero_gemini_calls": True,
    }


ledger_raw = str(os.environ.get("NOTE_DELIVERY_LEDGER_PATH", "")).strip()
sync_id = normalized(os.environ.get("NOTE_TARGET_SYNC_ID", "")).lower()
note_target = normalized(os.environ.get("NOTE_TARGET_IDENTITY", ""))
result_file = str(os.environ.get("NOTE_DRAFT_RESULT_FILE", "")).strip()
manual_token = str(os.environ.get("NOTE_TERRA_MANUAL_RECREATE_TOKEN", "") or "")
if manual_token and (
    manual_token != "ASSUME_ABSENT_TERRA_ONCE"
    or sync_id != "40a479ffdca981efb47bc5fe5fee1da9"
    or note_target != "trendhub_biz"
):
    raise LedgerUnavailableError("terra_manual_preflight_not_authorized")

if not ledger_raw:
    raise LedgerUnavailableError("ledger_gate_path_missing")
if not sync_id or not note_target:
    raise LedgerUnavailableError("ledger_gate_identity_missing")

ledger_path = Path(ledger_raw).expanduser()
if not ledger_path.is_file():
    raise LedgerUnavailableError("ledger_gate_missing")

conn = None
try:
    uri = ledger_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")

    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version != SQLITE_SCHEMA_VERSION:
        raise LedgerSchemaError("unsupported_ledger_schema")

    tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if not {"deliveries", "logical_bindings", "delivery_events"}.issubset(tables):
        raise LedgerSchemaError("incomplete_ledger_schema")

    logical_key = logical_key_for_identity(sync_id, note_target)
    row = conn.execute(
        "SELECT d.schema_version, d.state, d.record_id, d.stable_draft_id, "
        "d.note_host, d.operation_key, b.draft_id AS bound_draft_id "
        "FROM logical_bindings b JOIN deliveries d ON d.operation_key=b.operation_key "
        "WHERE b.logical_key=?",
        (logical_key,),
    ).fetchone()

    if row is None:
        # A one-off exception MUST have an existing ambiguous intent.
        result = safe_result(
            "ledger_blocked_ambiguous", False
        ) if manual_token else safe_result("ledger_clean_new", True)
    else:
        if str(row["schema_version"] or "") != DELIVERY_RECORD_SCHEMA_VERSION:
            raise LedgerSchemaError("unsupported_delivery_record_schema")
        try:
            state = DeliveryState(str(row["state"] or ""))
        except ValueError as exc:
            raise LedgerSchemaError("unknown_delivery_state") from exc

        if manual_token:
            prior = conn.execute(
                "SELECT 1 FROM delivery_events "
                "WHERE record_id=? AND category='owner_assumed_absent_once' LIMIT 1",
                (row["record_id"],),
            ).fetchone()
            authorized_once = (
                state == DeliveryState.CREATION_UNKNOWN and prior is None and
                not row["stable_draft_id"] and not row["note_host"] and
                not row["bound_draft_id"]
            )
            result = safe_result(
                "terra_owner_manual_intent_eligible" if authorized_once
                else "ledger_blocked_ambiguous", authorized_once,
            )
        elif state in {
            DeliveryState.DRAFT_VERIFIED,
            DeliveryState.QUEUE_CONFIRMATION_PENDING,
            DeliveryState.QUEUE_CONFIRMED,
        }:
            result = safe_result("ledger_reconcile_existing", True)
        else:
            result = safe_result("ledger_blocked_ambiguous", False)
finally:
    if conn is not None:
        conn.close()

if result_file:
    path = Path(result_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

print(
    "[P0B LEDGER PREFLIGHT] "
    + json.dumps(
        {
            "status": result["status"],
            "should_run_delivery": result["should_run_delivery"],
            "zero_gemini_calls": True,
        },
        ensure_ascii=False,
    )
)
PY
