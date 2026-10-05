import json
import threading
from dataclasses import replace

import pytest

from note_document_contract import Document, Paragraph, Text
from note_delivery_ledger import (
    ConcurrentStateChange,
    DeliveryState,
    LedgerSchemaError,
    build_delivery_snapshot,
    logical_delivery_key,
    operation_key,
)
from note_delivery_gcs import GCSDeliveryLedger, record_object_name


class NotFound(Exception):
    pass


class PreconditionFailed(Exception):
    pass


class FakeBlob:
    def __init__(self, bucket, name):
        self.bucket = bucket
        self.name = name
        self.generation = None

    def reload(self):
        with self.bucket.lock:
            entry = self.bucket.store.get(self.name)
            if entry is None:
                raise NotFound(self.name)
            self.generation = entry[0]

    def download_as_text(self):
        with self.bucket.lock:
            entry = self.bucket.store.get(self.name)
            if entry is None:
                raise NotFound(self.name)
            self.generation = entry[0]
            return entry[1]

    def upload_from_string(self, data, *, content_type=None, if_generation_match=None):
        del content_type
        with self.bucket.lock:
            current = self.bucket.store.get(self.name)
            current_generation = 0 if current is None else current[0]
            self.bucket.upload_conditions.append(if_generation_match)
            if self.bucket.fail_next_precondition:
                self.bucket.fail_next_precondition = False
                raise PreconditionFailed('forced')
            if if_generation_match is None:
                raise AssertionError('unconditional GCS overwrite attempted')
            if if_generation_match == 0:
                if current is not None:
                    raise PreconditionFailed('already exists')
            elif current is None or int(if_generation_match) != current_generation:
                raise PreconditionFailed('stale generation')
            new_generation = current_generation + 1
            self.bucket.store[self.name] = (new_generation, str(data))
            self.generation = new_generation


class FakeBucket:
    def __init__(self):
        self.store = {}
        self.upload_conditions = []
        self.fail_next_precondition = False
        self.lock = threading.Lock()

    def blob(self, name):
        return FakeBlob(self, name)

    def list_blobs(self, *, prefix):
        with self.lock:
            names = [name for name in sorted(self.store) if name.startswith(prefix)]
        blobs = []
        for name in names:
            blob = FakeBlob(self, name)
            blob.reload()
            blobs.append(blob)
        return blobs


class FakeClient:
    def __init__(self):
        self.bucket_obj = FakeBucket()

    def bucket(self, _name):
        return self.bucket_obj


def _snapshot(**overrides):
    values = dict(
        sync_id='sync-001',
        queue_page_id='page-001',
        title='Hosted GCS delivery',
        manuscript_sha256='1' * 64,
        publication_policy_sha256='2' * 64,
        document=Document((Paragraph((Text('Body'),)),)),
        transform_versions=(('run222', 'v1'),),
        eyecatch_sha256='3' * 64,
        eyecatch_asset_id='asset-1',
        note_target='trendhub-biz',
        ready_provenance='ready:v1',
    )
    values.update(overrides)
    return build_delivery_snapshot(**values)


def _ledger(client=None):
    return GCSDeliveryLedger('private-test-bucket', client=client or FakeClient())


def test_record_object_name_is_deterministic_and_opaque():
    snapshot = _snapshot()
    logical = logical_delivery_key(snapshot)
    name = record_object_name(logical)
    assert name == record_object_name(logical)
    assert logical in name
    assert snapshot.sync_id not in name
    assert snapshot.note_target not in name


def test_first_begin_or_load_uses_generation_zero_and_authorizes_one_create():
    client = FakeClient()
    ledger = _ledger(client)
    decision = ledger.begin_or_load(_snapshot(), run_correlation_id='run-a')
    assert decision.creation_authorized is True
    assert decision.record.state == DeliveryState.CREATE_INTENT_RECORDED
    assert client.bucket_obj.upload_conditions == [0]


def test_same_operation_retry_reuses_existing_record_and_never_recreates():
    client = FakeClient()
    ledger = _ledger(client)
    first = ledger.begin_or_load(_snapshot(), run_correlation_id='run-a')
    retry = ledger.begin_or_load(_snapshot(), run_correlation_id='run-b')
    assert first.creation_authorized is True
    assert retry.creation_authorized is False
    assert retry.reason == 'existing_operation'
    assert retry.record.operation_key == first.record.operation_key
    assert all(condition is not None for condition in client.bucket_obj.upload_conditions)


def test_different_revision_cannot_bypass_active_logical_delivery():
    client = FakeClient()
    ledger = _ledger(client)
    first = ledger.begin_or_load(_snapshot(), run_correlation_id='run-a')
    changed = _snapshot(manuscript_sha256='9' * 64)
    second = ledger.begin_or_load(changed, run_correlation_id='run-b')
    assert first.creation_authorized is True
    assert second.creation_authorized is False
    assert second.reason == 'active_logical_delivery'
    assert second.record.operation_key == first.record.operation_key
    assert second.record.operation_key != operation_key(changed)


def test_stale_generation_transition_maps_to_concurrent_state_change():
    client = FakeClient()
    ledger = _ledger(client)
    created = ledger.begin_or_load(_snapshot(), run_correlation_id='run-a').record
    client.bucket_obj.fail_next_precondition = True
    with pytest.raises(ConcurrentStateChange, match='state_generation_mismatch'):
        ledger.record_draft_created(
            created.operation_key,
            draft_id='opaque-draft-1',
            note_host='note.com',
            expected_version=created.state_version,
        )


def test_generation_guarded_transition_records_audit_event_in_same_object():
    client = FakeClient()
    ledger = _ledger(client)
    intent = ledger.begin_or_load(_snapshot(), run_correlation_id='run-a').record
    created = ledger.record_draft_created(
        intent.operation_key,
        draft_id='opaque-draft-1',
        note_host='note.com',
        expected_version=intent.state_version,
    )
    name = record_object_name(intent.logical_key)
    envelope = json.loads(client.bucket_obj.store[name][1])
    assert created.state == DeliveryState.DRAFT_CREATED
    assert [event['new_state'] for event in envelope['events']] == [
        DeliveryState.CREATE_INTENT_RECORDED.value,
        DeliveryState.DRAFT_CREATED.value,
    ]
    assert client.bucket_obj.upload_conditions == [0, 1]


def test_malformed_cloud_record_fails_closed():
    client = FakeClient()
    snapshot = _snapshot()
    name = record_object_name(logical_delivery_key(snapshot))
    client.bucket_obj.store[name] = (1, '{not-json')
    ledger = _ledger(client)
    with pytest.raises(LedgerSchemaError, match='invalid_cloud_ledger_record'):
        ledger.get_active_by_logical_key(logical_delivery_key(snapshot))


def test_two_ledgers_share_one_creation_authority():
    client = FakeClient()
    first = _ledger(client)
    second = _ledger(client)
    decisions = [
        first.begin_or_load(_snapshot(), run_correlation_id='run-a'),
        second.begin_or_load(_snapshot(), run_correlation_id='run-b'),
    ]
    assert sorted(item.creation_authorized for item in decisions) == [False, True]
    assert len({item.record.operation_key for item in decisions}) == 1
    assert all(condition is not None for condition in client.bucket_obj.upload_conditions)
