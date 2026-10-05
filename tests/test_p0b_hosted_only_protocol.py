from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol, runtime_checkable

import pytest

from note_document_contract import Document, Paragraph, Text
from note_delivery_ledger import (
    DELIVERY_RECORD_SCHEMA_VERSION,
    DeliveryLedger,
    DeliveryRecord,
    DeliveryState,
    LedgerSchemaError,
    SQLiteDeliveryLedger,
    build_delivery_snapshot,
    delivery_record_from_dict,
    delivery_record_to_dict,
)


def _snapshot():
    return build_delivery_snapshot(
        sync_id="sync-001",
        queue_page_id="queue-page-1",
        title="Hosted-only delivery",
        manuscript_sha256="1" * 64,
        publication_policy_sha256="2" * 64,
        document=Document((Paragraph((Text("Body"),)),)),
        transform_versions=(("run222", "v1"),),
        eyecatch_sha256="3" * 64,
        eyecatch_asset_id="asset-1",
        note_target="trendhub-biz",
        ready_provenance="ready:v1",
    )


def _record():
    snap = _snapshot()
    return DeliveryRecord(
        record_id="opaque-record",
        schema_version=DELIVERY_RECORD_SCHEMA_VERSION,
        logical_key="a" * 64,
        revision_key="b" * 64,
        operation_key="c" * 64,
        snapshot=snap,
        state=DeliveryState.CREATE_INTENT_RECORDED,
        state_version=1,
        attempt_count=1,
        owner_correlation_id="run-a",
        owner_expires_at=None,
        created_at="2026-10-06T00:00:00Z",
        updated_at="2026-10-06T00:00:00Z",
        draft_id=None,
        note_host=None,
        last_verified_canonical_hash=None,
        queue_receipt_digest=None,
        conflict_category=None,
    )


def test_delivery_record_round_trips_through_shared_serialization():
    record = _record()
    assert delivery_record_from_dict(delivery_record_to_dict(record)) == record


def test_shared_deserializer_rejects_unsupported_record_schema():
    payload = delivery_record_to_dict(_record())
    payload["schema_version"] = "unsupported"
    with pytest.raises(LedgerSchemaError, match="unsupported_ledger_schema"):
        delivery_record_from_dict(payload)


def test_shared_deserializer_rejects_invalid_state():
    payload = delivery_record_to_dict(_record())
    payload["state"] = "NOT_A_STATE"
    with pytest.raises(LedgerSchemaError, match="invalid_ledger_state"):
        delivery_record_from_dict(payload)


def test_sqlite_reference_adapter_satisfies_storage_neutral_protocol():
    with TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        assert isinstance(ledger, DeliveryLedger)
