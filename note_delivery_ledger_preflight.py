from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import unicodedata
from typing import Any

from note_delivery_ledger import (
    DELIVERY_RECORD_SCHEMA_VERSION,
    DESTINATION_SURFACE,
    LOGICAL_KEY_SCHEMA_VERSION,
    SQLITE_SCHEMA_VERSION,
    DeliveryState,
    LedgerSchemaError,
    LedgerUnavailableError,
)


_AUTOMATICALLY_RECONCILABLE = frozenset(
    {
        DeliveryState.DRAFT_VERIFIED,
        DeliveryState.QUEUE_CONFIRMATION_PENDING,
        DeliveryState.QUEUE_CONFIRMED,
    }
)


def _normalized_text(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).strip()


def _logical_key_for_identity(sync_id: str, note_target: str) -> str:
    material = {
        "schema_version": LOGICAL_KEY_SCHEMA_VERSION,
        "sync_id": _normalized_text(sync_id).lower(),
        "note_target": _normalized_text(note_target),
        "destination_surface": DESTINATION_SURFACE,
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_result(status: str, should_run_delivery: bool) -> dict[str, Any]:
    return {
        "status": status,
        "should_run_delivery": bool(should_run_delivery),
        "zero_gemini_calls": True,
    }


def read_only_delivery_gate(
    path: str | os.PathLike[str],
    *,
    sync_id: str,
    note_target: str,
) -> dict[str, Any]:
    """Read durable delivery authority without mutating or initializing the ledger.

    The gate intentionally treats a missing ledger as unavailable rather than empty. On the
    persistent production VM, silently recreating a missing ledger could erase the only evidence
    that a prior note creation was externally ambiguous.
    """
    normalized_sync = _normalized_text(sync_id).lower()
    normalized_target = _normalized_text(note_target)
    if not normalized_sync or not normalized_target:
        raise LedgerUnavailableError("ledger_gate_identity_missing")

    ledger_path = Path(path).expanduser()
    if not ledger_path.is_file():
        raise LedgerUnavailableError("ledger_gate_missing")

    conn: sqlite3.Connection | None = None
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

        logical_key = _logical_key_for_identity(normalized_sync, normalized_target)
        row = conn.execute(
            "SELECT d.schema_version, d.state, d.stable_draft_id "
            "FROM logical_bindings b JOIN deliveries d ON d.operation_key=b.operation_key "
            "WHERE b.logical_key=?",
            (logical_key,),
        ).fetchone()
        if row is None:
            return _safe_result("ledger_clean_new", True)

        if str(row["schema_version"] or "") != DELIVERY_RECORD_SCHEMA_VERSION:
            raise LedgerSchemaError("unsupported_delivery_record_schema")
        try:
            state = DeliveryState(str(row["state"] or ""))
        except ValueError as exc:
            raise LedgerSchemaError("unknown_delivery_state") from exc

        if state in _AUTOMATICALLY_RECONCILABLE:
            return _safe_result("ledger_reconcile_existing", True)

        return _safe_result("ledger_blocked_ambiguous", False)
    except (LedgerSchemaError, LedgerUnavailableError):
        raise
    except (OSError, sqlite3.Error) as exc:
        raise LedgerUnavailableError("ledger_gate_read_failed") from exc
    finally:
        if conn is not None:
            conn.close()


def _write_result(result: dict[str, Any]) -> None:
    target = str(os.environ.get("NOTE_DRAFT_RESULT_FILE", "")).strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ledger_path = str(os.environ.get("NOTE_DELIVERY_LEDGER_PATH", "")).strip()
    sync_id = str(os.environ.get("NOTE_TARGET_SYNC_ID", "")).strip()
    note_target = str(os.environ.get("NOTE_TARGET_IDENTITY", "")).strip()
    if not ledger_path:
        raise LedgerUnavailableError("ledger_gate_path_missing")

    result = read_only_delivery_gate(
        ledger_path,
        sync_id=sync_id,
        note_target=note_target,
    )
    _write_result(result)
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


if __name__ == "__main__":
    main()
