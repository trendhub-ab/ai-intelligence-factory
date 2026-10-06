#!/usr/bin/env python3
"""Fail-closed phase-one reconciliation for one P0-B strong-zero census.

This module does not create, edit, verify, publish, or bind a note draft. It only turns an
existing CREATION_UNKNOWN durable record into MANUAL_RECONCILIATION_REQUIRED after a strict
read-only census proves strong_zero. The transition deliberately does not restore creation
authority; any future retry must be a separate, explicitly designed operation.
"""
from __future__ import annotations

from typing import Any, Mapping

import note_delivery_runtime as delivery_runtime
from note_delivery_ledger import DeliveryLedger, DeliverySnapshot, DeliveryState
from note_delivery_strong_zero import (
    EVIDENCE_CATEGORY_PREFIX,
    StrongZeroEvidenceError,
    strong_zero_evidence_digest,
    validate_strong_zero_census,
)


class StrongZeroReconciliationError(RuntimeError):
    pass


def _normalized_identity(sync_id: str, note_target: str) -> tuple[str, str]:
    normalized_sync = str(sync_id or "").strip().lower()
    normalized_target = str(note_target or "").strip()
    if len(normalized_sync) != 32 or not normalized_target:
        raise StrongZeroReconciliationError("exact recovery identity is required")
    return normalized_sync, normalized_target


def reconcile_strong_zero(
    ledger: DeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
    current_snapshot: DeliverySnapshot,
    census: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist strong-zero reconciliation without granting any new creation authority."""
    normalized_sync, normalized_target = _normalized_identity(sync_id, note_target)
    try:
        safe_census = validate_strong_zero_census(census)
    except StrongZeroEvidenceError as exc:
        raise StrongZeroReconciliationError(str(exc)) from exc

    logical_key = delivery_runtime._logical_key_for_identity(normalized_sync, normalized_target)
    record = ledger.get_active_by_logical_key(logical_key)
    if record is None:
        raise StrongZeroReconciliationError("durable delivery is unavailable for reconciliation")
    if record.state != DeliveryState.CREATION_UNKNOWN:
        raise StrongZeroReconciliationError("durable delivery is not CREATION_UNKNOWN")
    if str(record.draft_id or "").strip():
        raise StrongZeroReconciliationError("ambiguous delivery already has a stable draft identity")
    if record.snapshot.sync_id != normalized_sync or record.snapshot.note_target != normalized_target:
        raise StrongZeroReconciliationError("durable delivery identity mismatch")
    if current_snapshot != record.snapshot:
        raise StrongZeroReconciliationError(
            "current delivery snapshot differs from ambiguous attempt"
        )

    digest = strong_zero_evidence_digest(safe_census)
    category = f"{EVIDENCE_CATEGORY_PREFIX}{digest}"
    updated = ledger.record_blocked(
        record.operation_key,
        state=DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        category=category,
        expected_version=record.state_version,
    )
    return {
        "status": "strong_zero_reconciled_no_create_authority",
        "prior_state": record.state.value,
        "state": updated.state.value,
        "state_version": updated.state_version,
        "creation_authorized": False,
        "note_mutation_count": 0,
        "zero_model_calls": True,
        "public_release": False,
        "evidence_digest": digest,
    }
