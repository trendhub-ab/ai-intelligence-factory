from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from typing import Any
from uuid import uuid4

from note_delivery_ledger import (
    DELIVERY_RECORD_SCHEMA_VERSION,
    ConcurrentStateChange,
    DeliveryRecord,
    DeliverySnapshot,
    DeliveryState,
    IntentDecision,
    InvalidStateTransition,
    LedgerSchemaError,
    LedgerUnavailableError,
    _ALLOWED_TRANSITIONS,
    _normalized_text,
    _utc_now,
    delivery_record_from_dict,
    delivery_record_to_dict,
    logical_delivery_key,
    operation_key,
    revision_key,
)

GCS_LEDGER_ENVELOPE_SCHEMA_VERSION = "note-delivery-gcs-envelope-v1"
DEFAULT_PREFIX = "delivery/v1"


def record_object_name(logical_key: str, prefix: str = DEFAULT_PREFIX) -> str:
    clean_prefix = str(prefix or DEFAULT_PREFIX).strip().strip("/") or DEFAULT_PREFIX
    logical = str(logical_key or "").strip().lower()
    if not logical:
        raise LedgerSchemaError("logical_key_required")
    return f"{clean_prefix}/records/{logical}.json"


def _is_not_found(exc: BaseException) -> bool:
    return exc.__class__.__name__ == "NotFound"


def _is_precondition_failure(exc: BaseException) -> bool:
    return exc.__class__.__name__ in {"PreconditionFailed", "Conflict"}


def _event(
    *,
    prior_state: DeliveryState,
    new_state: DeliveryState,
    category: str,
    run_correlation_id: str | None,
    state_version: int,
    created_at: str,
) -> dict[str, object]:
    return {
        "prior_state": prior_state.value,
        "new_state": new_state.value,
        "category": _normalized_text(category),
        "run_correlation_id": None if run_correlation_id is None else _normalized_text(run_correlation_id),
        "state_version": int(state_version),
        "created_at": created_at,
    }


class GCSDeliveryLedger:
    def __init__(
        self,
        bucket_name: str,
        *,
        prefix: str = DEFAULT_PREFIX,
        client: object | None = None,
    ):
        self.bucket_name = str(bucket_name or "").strip()
        if not self.bucket_name:
            raise LedgerUnavailableError("gcs_bucket_required")
        self.prefix = str(prefix or DEFAULT_PREFIX).strip().strip("/") or DEFAULT_PREFIX
        if client is None:
            try:
                from google.cloud import storage
            except Exception as exc:
                raise LedgerUnavailableError("gcs_client_unavailable") from exc
            try:
                client = storage.Client()
            except Exception as exc:
                raise LedgerUnavailableError("gcs_client_unavailable") from exc
        self.client = client
        try:
            self.bucket = self.client.bucket(self.bucket_name)
        except Exception as exc:
            raise LedgerUnavailableError("gcs_bucket_unavailable") from exc

    def initialize(self) -> None:
        """Validate read/list access without mutating durable ledger state."""
        try:
            blobs = self.bucket.list_blobs(prefix=f"{self.prefix}/records/")
            for _blob in blobs:
                break
        except Exception as exc:
            raise LedgerUnavailableError("gcs_ledger_initialize_failed") from exc

    def _name(self, logical_key: str) -> str:
        return record_object_name(logical_key, self.prefix)

    def _decode_envelope(self, raw: str) -> tuple[DeliveryRecord, list[dict[str, object]]]:
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise LedgerSchemaError("invalid_cloud_ledger_record") from exc
        if not isinstance(data, dict):
            raise LedgerSchemaError("invalid_cloud_ledger_record")
        if str(data.get("schema_version") or "") != GCS_LEDGER_ENVELOPE_SCHEMA_VERSION:
            raise LedgerSchemaError("invalid_cloud_ledger_record")
        events = data.get("events")
        if not isinstance(events, list):
            raise LedgerSchemaError("invalid_cloud_ledger_record")
        try:
            record = delivery_record_from_dict(data.get("record"))
        except (LedgerSchemaError, TypeError, ValueError) as exc:
            raise LedgerSchemaError("invalid_cloud_ledger_record") from exc
        return record, [dict(item) for item in events if isinstance(item, dict)]

    def _encode_envelope(self, record: DeliveryRecord, events: list[dict[str, object]]) -> str:
        return json.dumps(
            {
                "schema_version": GCS_LEDGER_ENVELOPE_SCHEMA_VERSION,
                "record": delivery_record_to_dict(record),
                "events": events,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _load_by_logical_key(
        self, logical_key: str
    ) -> tuple[DeliveryRecord, list[dict[str, object]], int] | None:
        blob = self.bucket.blob(self._name(logical_key))
        try:
            raw = blob.download_as_text()
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise LedgerUnavailableError("gcs_ledger_read_failed") from exc
        try:
            generation = int(blob.generation)
        except Exception as exc:
            raise LedgerUnavailableError("gcs_generation_missing") from exc
        record, events = self._decode_envelope(raw)
        if record.logical_key != logical_key:
            raise LedgerSchemaError("invalid_cloud_ledger_record")
        return record, events, generation

    def _write(
        self,
        logical_key: str,
        record: DeliveryRecord,
        events: list[dict[str, object]],
        *,
        expected_generation: int,
    ) -> int:
        blob = self.bucket.blob(self._name(logical_key))
        payload = self._encode_envelope(record, events)
        try:
            blob.upload_from_string(
                payload,
                content_type="application/json",
                if_generation_match=int(expected_generation),
            )
        except Exception as exc:
            if _is_precondition_failure(exc):
                raise ConcurrentStateChange("state_generation_mismatch") from exc
            raise LedgerUnavailableError("gcs_ledger_write_failed") from exc
        try:
            return int(blob.generation)
        except Exception as exc:
            raise LedgerUnavailableError("gcs_generation_missing") from exc

    def get_active_by_logical_key(self, logical_key: str) -> DeliveryRecord | None:
        loaded = self._load_by_logical_key(str(logical_key or "").strip().lower())
        return None if loaded is None else loaded[0]

    def get_by_operation_key(self, op_key: str) -> DeliveryRecord | None:
        target = str(op_key or "").strip().lower()
        if not target:
            return None
        prefix = f"{self.prefix}/records/"
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                try:
                    raw = blob.download_as_text()
                except Exception as exc:
                    raise LedgerUnavailableError("gcs_ledger_read_failed") from exc
                record, _events = self._decode_envelope(raw)
                if record.operation_key == target:
                    return record
        except LedgerSchemaError:
            raise
        except LedgerUnavailableError:
            raise
        except Exception as exc:
            raise LedgerUnavailableError("gcs_ledger_list_failed") from exc
        return None

    def begin_or_load(self, snapshot: DeliverySnapshot, *, run_correlation_id: str) -> IntentDecision:
        logical_key = logical_delivery_key(snapshot)
        op_key = operation_key(snapshot)
        loaded = self._load_by_logical_key(logical_key)
        if loaded is not None:
            current, events, generation = loaded
            if current.operation_key == op_key:
                updated = replace(
                    current,
                    attempt_count=current.attempt_count + 1,
                    updated_at=_utc_now(),
                )
                try:
                    self._write(logical_key, updated, events, expected_generation=generation)
                    current = updated
                except ConcurrentStateChange:
                    refreshed = self._load_by_logical_key(logical_key)
                    if refreshed is None:
                        raise LedgerUnavailableError("gcs_ledger_invariant_missing")
                    current = refreshed[0]
                return IntentDecision(current, False, "existing_operation")
            return IntentDecision(current, False, "active_logical_delivery")

        now = _utc_now()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        record = DeliveryRecord(
            record_id=uuid4().hex,
            schema_version=DELIVERY_RECORD_SCHEMA_VERSION,
            logical_key=logical_key,
            revision_key=revision_key(snapshot),
            operation_key=op_key,
            snapshot=snapshot,
            state=DeliveryState.CREATE_INTENT_RECORDED,
            state_version=1,
            attempt_count=1,
            owner_correlation_id=_normalized_text(run_correlation_id),
            owner_expires_at=expires,
            created_at=now,
            updated_at=now,
            draft_id=None,
            note_host=None,
            last_verified_canonical_hash=None,
            queue_receipt_digest=None,
            conflict_category=None,
        )
        events = [
            _event(
                prior_state=DeliveryState.PREPARED,
                new_state=DeliveryState.CREATE_INTENT_RECORDED,
                category="create_intent_recorded",
                run_correlation_id=record.owner_correlation_id,
                state_version=1,
                created_at=now,
            )
        ]
        try:
            self._write(logical_key, record, events, expected_generation=0)
            return IntentDecision(record, True, "creation_authorized")
        except ConcurrentStateChange:
            winner = self._load_by_logical_key(logical_key)
            if winner is None:
                raise LedgerUnavailableError("gcs_ledger_invariant_missing")
            winning_record = winner[0]
            reason = "existing_operation" if winning_record.operation_key == op_key else "active_logical_delivery"
            return IntentDecision(winning_record, False, reason)

    def _load_operation(
        self, op_key: str
    ) -> tuple[DeliveryRecord, list[dict[str, object]], int]:
        target = str(op_key or "").strip().lower()
        prefix = f"{self.prefix}/records/"
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                raw = blob.download_as_text()
                record, events = self._decode_envelope(raw)
                if record.operation_key == target:
                    try:
                        generation = int(blob.generation)
                    except Exception as exc:
                        raise LedgerUnavailableError("gcs_generation_missing") from exc
                    return record, events, generation
        except LedgerSchemaError:
            raise
        except LedgerUnavailableError:
            raise
        except Exception as exc:
            raise LedgerUnavailableError("gcs_ledger_read_failed") from exc
        raise InvalidStateTransition("delivery_not_found")

    def _transition(
        self,
        op_key: str,
        *,
        new_state: DeliveryState,
        expected_version: int,
        category: str,
        fields: dict[str, object] | None = None,
    ) -> DeliveryRecord:
        current, events, generation = self._load_operation(op_key)
        if current.state_version != expected_version:
            raise ConcurrentStateChange("state_version_mismatch")
        if new_state not in _ALLOWED_TRANSITIONS.get(current.state, frozenset()):
            raise InvalidStateTransition("invalid_state_transition")

        fields = dict(fields or {})
        allowed_fields = {
            "draft_id",
            "note_host",
            "last_verified_canonical_hash",
            "queue_receipt_digest",
            "conflict_category",
        }
        if any(key not in allowed_fields for key in fields):
            raise InvalidStateTransition("unsupported_transition_field")

        next_version = current.state_version + 1
        now = _utc_now()
        updated = replace(
            current,
            state=new_state,
            state_version=next_version,
            updated_at=now,
            **fields,
        )
        next_events = list(events)
        next_events.append(
            _event(
                prior_state=current.state,
                new_state=new_state,
                category=category,
                run_correlation_id=current.owner_correlation_id,
                state_version=next_version,
                created_at=now,
            )
        )
        self._write(current.logical_key, updated, next_events, expected_generation=generation)
        return updated

    def record_draft_created(
        self,
        operation_key: str,
        *,
        draft_id: str,
        note_host: str,
        expected_version: int,
    ) -> DeliveryRecord:
        draft_id = _normalized_text(draft_id)
        note_host = _normalized_text(note_host)
        if not draft_id or not note_host:
            raise InvalidStateTransition("draft_identity_required")
        return self._transition(
            operation_key,
            new_state=DeliveryState.DRAFT_CREATED,
            expected_version=expected_version,
            category="draft_created",
            fields={"draft_id": draft_id, "note_host": note_host},
        )

    def record_verified(
        self,
        operation_key: str,
        *,
        canonical_sha256: str,
        expected_version: int,
    ) -> DeliveryRecord:
        return self._transition(
            operation_key,
            new_state=DeliveryState.DRAFT_VERIFIED,
            expected_version=expected_version,
            category="draft_verified",
            fields={"last_verified_canonical_hash": _normalized_text(canonical_sha256)},
        )

    def record_queue_pending(
        self,
        operation_key: str,
        *,
        category: str,
        expected_version: int,
    ) -> DeliveryRecord:
        return self._transition(
            operation_key,
            new_state=DeliveryState.QUEUE_CONFIRMATION_PENDING,
            expected_version=expected_version,
            category=category,
            fields={"conflict_category": _normalized_text(category)},
        )

    def record_queue_confirmed(
        self,
        operation_key: str,
        *,
        receipt_digest: str,
        expected_version: int,
    ) -> DeliveryRecord:
        return self._transition(
            operation_key,
            new_state=DeliveryState.QUEUE_CONFIRMED,
            expected_version=expected_version,
            category="queue_confirmed",
            fields={
                "queue_receipt_digest": _normalized_text(receipt_digest),
                "conflict_category": None,
            },
        )

    def record_blocked(
        self,
        operation_key: str,
        *,
        state: DeliveryState,
        category: str,
        expected_version: int,
    ) -> DeliveryRecord:
        if state not in {
            DeliveryState.CREATION_UNKNOWN,
            DeliveryState.VERIFICATION_BLOCKED,
            DeliveryState.CONFLICT,
            DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        }:
            raise InvalidStateTransition("blocked_state_required")
        return self._transition(
            operation_key,
            new_state=state,
            expected_version=expected_version,
            category=category,
            fields={"conflict_category": _normalized_text(category)},
        )
