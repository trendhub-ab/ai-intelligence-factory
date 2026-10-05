#!/usr/bin/env python3
"""Apply a verified CREATION_UNKNOWN recovery without creating another note draft.

This module is intentionally separate from the read-only discovery module. It accepts only
an already losslessly verified, unique existing private draft identity and advances the
existing durable record through DRAFT_CREATED -> DRAFT_VERIFIED before reusing the normal
exact queue reconciliation path. It contains no note create or public-release action.
"""
from __future__ import annotations

from typing import Any, Mapping

import note_delivery_runtime as delivery_runtime
from note_delivery_ledger import (
    DeliveryLedgerError,
    DeliveryRecord,
    DeliveryState,
    SQLiteDeliveryLedger,
)


class CreationRecoveryApplyError(RuntimeError):
    pass


def _required_verified_identity(match: Mapping[str, Any]) -> tuple[str, str]:
    draft_id = str(match.get("draft_id") or "").strip()
    note_host = str(match.get("note_host") or "").strip().lower()
    route_hash = str(match.get("editor_route_hash") or "").strip()
    is_note_host = note_host == "note.com" or note_host.endswith(".note.com")
    if not draft_id or not route_hash or not is_note_host:
        raise CreationRecoveryApplyError("verified private draft identity is incomplete")
    return draft_id, note_host


def apply_verified_recovery(
    base: Any,
    ledger: SQLiteDeliveryLedger,
    record: DeliveryRecord,
    match: Mapping[str, Any],
) -> DeliveryRecord:
    """Bind one unique verified existing draft and resume exact queue reconciliation.

    The supplied record must still be the current durable CREATION_UNKNOWN record with no
    stable external identity. State/version are re-read before mutation so stale audit
    evidence cannot overwrite a newer reconciliation decision.
    """
    if record.state != DeliveryState.CREATION_UNKNOWN or str(record.draft_id or "").strip():
        raise CreationRecoveryApplyError("durable delivery is not recoverable CREATION_UNKNOWN")

    draft_id, note_host = _required_verified_identity(match)
    current = ledger.get_by_operation_key(record.operation_key)
    if (
        current is None
        or current.record_id != record.record_id
        or current.state != DeliveryState.CREATION_UNKNOWN
        or current.state_version != record.state_version
        or str(current.draft_id or "").strip()
    ):
        raise CreationRecoveryApplyError("durable recovery state changed after audit")

    canonical_sha256 = str(current.snapshot.canonical_document_sha256 or "").strip().lower()
    if not canonical_sha256:
        raise CreationRecoveryApplyError("ambiguous delivery has no canonical recovery hash")

    try:
        created = ledger.record_draft_created(
            current.operation_key,
            draft_id=draft_id,
            note_host=note_host,
            expected_version=current.state_version,
        )
        verified = ledger.record_verified(
            current.operation_key,
            canonical_sha256=canonical_sha256,
            expected_version=created.state_version,
        )
        return delivery_runtime._reconcile_queue_projection(base, ledger, verified)
    except DeliveryLedgerError as exc:
        raise CreationRecoveryApplyError("durable recovery apply failed") from exc
