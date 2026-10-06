#!/usr/bin/env python3
"""Fail-closed phase-one reconciliation for one P0-B strong-zero census.

This module does not create, edit, verify, publish, or bind a note draft. It only turns an
existing CREATION_UNKNOWN durable record into MANUAL_RECONCILIATION_REQUIRED after a strict
read-only census proves strong_zero. The transition deliberately does not restore creation
authority; any future retry must be a separate, explicitly designed operation.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import note_delivery_runtime as delivery_runtime
from note_delivery_ledger import DeliveryLedger, DeliveryState


class StrongZeroReconciliationError(RuntimeError):
    pass


_CENSUS_KEYS = frozenset(
    {
        "status",
        "authenticated",
        "private_note_card_count",
        "exact_target_count",
        "suspicious_blank_count",
        "unreadable_count",
        "decision",
        "zero_model_calls",
        "mutation_count",
    }
)
_CATEGORY_PREFIX = "creation_absence_confirmed_strong_zero"


def _normalized_identity(sync_id: str, note_target: str) -> tuple[str, str]:
    normalized_sync = str(sync_id or "").strip().lower()
    normalized_target = str(note_target or "").strip()
    if len(normalized_sync) != 32 or not normalized_target:
        raise StrongZeroReconciliationError("exact recovery identity is required")
    return normalized_sync, normalized_target


def _validated_strong_zero(census: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(census, Mapping) or set(census) != _CENSUS_KEYS:
        raise StrongZeroReconciliationError("strong-zero census schema mismatch")
    safe = {key: census[key] for key in sorted(_CENSUS_KEYS)}
    if safe["status"] != "census_complete_no_mutation":
        raise StrongZeroReconciliationError("census did not complete safely")
    if safe["authenticated"] is not True:
        raise StrongZeroReconciliationError("census authentication was not proven")
    if safe["decision"] != "strong_zero":
        raise StrongZeroReconciliationError("census is not strong_zero")
    if safe["zero_model_calls"] is not True or safe["mutation_count"] != 0:
        raise StrongZeroReconciliationError("census was not zero-model read-only")
    if int(safe["private_note_card_count"] or 0) <= 0:
        raise StrongZeroReconciliationError("private draft surface was not observable")
    if int(safe["exact_target_count"] or 0) != 0:
        raise StrongZeroReconciliationError("target draft is still observable")
    if int(safe["suspicious_blank_count"] or 0) != 0:
        raise StrongZeroReconciliationError("census contains suspicious blank cards")
    if int(safe["unreadable_count"] or 0) != 0:
        raise StrongZeroReconciliationError("census contains unreadable cards")
    return safe


def _evidence_digest(census: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(census),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reconcile_strong_zero(
    ledger: DeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
    census: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist strong-zero reconciliation without granting any new creation authority."""
    normalized_sync, normalized_target = _normalized_identity(sync_id, note_target)
    safe_census = _validated_strong_zero(census)
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

    digest = _evidence_digest(safe_census)
    category = f"{_CATEGORY_PREFIX}:{digest}"
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
