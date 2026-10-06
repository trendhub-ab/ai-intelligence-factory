#!/usr/bin/env python3
"""Bounded strong-zero retry orchestration for P0-B durable delivery."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import note_delivery_runtime as delivery_runtime
from note_delivery_ledger import DeliveryLedger, DeliveryRecord, DeliverySnapshot, DeliveryState
from note_delivery_strong_zero import (
    EVIDENCE_CATEGORY_PREFIX,
    StrongZeroEvidenceError,
    parse_strong_zero_evidence_category,
    strong_zero_evidence_digest,
    validate_strong_zero_census,
)


class StrongZeroRetryError(RuntimeError):
    pass


def _normalized_identity(sync_id: str, note_target: str) -> tuple[str, str]:
    normalized_sync = str(sync_id or "").strip().lower()
    normalized_target = str(note_target or "").strip()
    if len(normalized_sync) != 32 or not normalized_target:
        raise StrongZeroRetryError("exact retry identity is required")
    return normalized_sync, normalized_target


def _active_record(
    ledger: DeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
) -> DeliveryRecord:
    logical_key = delivery_runtime._logical_key_for_identity(sync_id, note_target)
    record = ledger.get_active_by_logical_key(logical_key)
    if record is None:
        raise StrongZeroRetryError("durable delivery is unavailable for retry")
    if record.snapshot.sync_id != sync_id or record.snapshot.note_target != note_target:
        raise StrongZeroRetryError("durable delivery identity mismatch")
    return record


def _validated_census(census: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return validate_strong_zero_census(census)
    except StrongZeroEvidenceError as exc:
        raise StrongZeroRetryError(str(exc)) from exc


def _retained_evidence_digest(record: DeliveryRecord) -> str:
    try:
        return parse_strong_zero_evidence_category(record.conflict_category or "")
    except StrongZeroEvidenceError as exc:
        raise StrongZeroRetryError("durable strong-zero evidence is invalid") from exc


def _utc_datetime(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise StrongZeroRetryError("retry owner lease is unavailable")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StrongZeroRetryError("retry owner lease is invalid") from exc
    if parsed.tzinfo is None:
        raise StrongZeroRetryError("retry owner lease is invalid")
    return parsed.astimezone(timezone.utc)


def run_reconciled_retry(
    base: Any,
    ledger: DeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
    current_snapshot: DeliverySnapshot,
    census: Mapping[str, Any],
    run_correlation_id: str,
    expected_version: int,
) -> DeliveryRecord:
    """Authorize and execute one retry only after fresh strong-zero evidence validates."""
    normalized_sync, normalized_target = _normalized_identity(sync_id, note_target)
    _validated_census(census)
    record = _active_record(
        ledger,
        sync_id=normalized_sync,
        note_target=normalized_target,
    )
    if record.state != DeliveryState.MANUAL_RECONCILIATION_REQUIRED:
        raise StrongZeroRetryError("durable delivery is not MANUAL_RECONCILIATION_REQUIRED")
    if str(record.draft_id or "").strip():
        raise StrongZeroRetryError("durable delivery already has a stable draft identity")
    if current_snapshot != record.snapshot:
        raise StrongZeroRetryError("current delivery snapshot differs from reconciled attempt")
    if int(expected_version) != record.state_version:
        raise StrongZeroRetryError("state_version_mismatch")
    _retained_evidence_digest(record)

    prepared = delivery_runtime.prepare_delivery(base, normalized_sync)
    if prepared.snapshot != current_snapshot:
        try:
            prepared.eyecatch_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise StrongZeroRetryError("reconstructed snapshot differs from current snapshot")

    return delivery_runtime.create_reconciled_retry(
        base,
        ledger,
        prepared,
        run_correlation_id=run_correlation_id,
        expected_version=expected_version,
    )


def reconcile_expired_retry_intent(
    ledger: DeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
    current_snapshot: DeliverySnapshot,
    census: Mapping[str, Any],
    now: datetime | None = None,
) -> DeliveryRecord:
    """Return an expired consumed retry intent to manual review; never grant creation authority."""
    normalized_sync, normalized_target = _normalized_identity(sync_id, note_target)
    safe_census = _validated_census(census)
    record = _active_record(
        ledger,
        sync_id=normalized_sync,
        note_target=normalized_target,
    )
    if record.state != DeliveryState.CREATE_INTENT_RECORDED:
        raise StrongZeroRetryError("durable retry intent is not CREATE_INTENT_RECORDED")
    if str(record.draft_id or "").strip():
        raise StrongZeroRetryError("retry intent already has a stable draft identity")
    if current_snapshot != record.snapshot:
        raise StrongZeroRetryError("current delivery snapshot differs from retry intent")
    _retained_evidence_digest(record)

    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        raise StrongZeroRetryError("current time must be timezone-aware")
    observed_now = observed_now.astimezone(timezone.utc)
    if observed_now <= _utc_datetime(record.owner_expires_at or ""):
        raise StrongZeroRetryError("retry owner lease has not expired")

    digest = strong_zero_evidence_digest(safe_census)
    return ledger.record_blocked(
        record.operation_key,
        state=DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        category=f"{EVIDENCE_CATEGORY_PREFIX}{digest}",
        expected_version=record.state_version,
    )
