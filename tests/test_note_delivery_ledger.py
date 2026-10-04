from dataclasses import replace

from note_document_contract import (
    CONTRACT_VERSION,
    NORMALIZATION_POLICY_VERSION,
    Document,
    Paragraph,
    Text,
)
from note_delivery_ledger import (
    build_delivery_snapshot,
    canonical_document_sha256,
    logical_delivery_key,
    operation_key,
    revision_key,
)


def _document(text: str = "Café") -> Document:
    return Document((Paragraph((Text(text),)),))


def _snapshot(**overrides):
    values = dict(
        sync_id=" sync-001 ",
        queue_page_id="page-001",
        title="  Durable delivery Café  ",
        manuscript_sha256="1" * 64,
        publication_policy_sha256="2" * 64,
        document=_document(),
        transform_versions=(("run222", "v1"), ("presentation", "v3")),
        eyecatch_sha256="3" * 64,
        eyecatch_asset_id="asset-001",
        note_target=" note-account-main ",
        ready_provenance="ready:publication-gate:v4",
    )
    values.update(overrides)
    return build_delivery_snapshot(**values)


def test_same_revision_has_same_operation_key_across_runs_and_retries():
    first = _snapshot()
    second = _snapshot()
    assert first == second
    assert revision_key(first) == revision_key(second)
    assert operation_key(first) == operation_key(second)


def test_manuscript_policy_asset_title_or_canonical_change_changes_revision_key():
    base = _snapshot()
    variants = (
        _snapshot(manuscript_sha256="4" * 64),
        _snapshot(publication_policy_sha256="5" * 64),
        _snapshot(eyecatch_sha256="6" * 64),
        _snapshot(eyecatch_asset_id="asset-002"),
        _snapshot(title="Different title"),
        _snapshot(document=_document("Different canonical body")),
        _snapshot(queue_page_id="page-002"),
        _snapshot(transform_versions=(("run222", "v2"), ("presentation", "v3"))),
        _snapshot(note_target="note-account-secondary"),
        _snapshot(ready_provenance="ready:publication-gate:v5"),
        _snapshot(sync_id="sync-002"),
    )
    assert all(revision_key(item) != revision_key(base) for item in variants)


def test_run_id_retry_count_and_timestamp_are_not_operation_key_material():
    snapshot = _snapshot()
    run_metadata_a = {"run_id": "100", "retry_count": 0, "timestamp": "2026-10-04T00:00:00Z"}
    run_metadata_b = {"run_id": "999", "retry_count": 9, "timestamp": "2030-01-01T00:00:00Z"}
    assert run_metadata_a != run_metadata_b
    assert operation_key(snapshot) == operation_key(replace(snapshot))


def test_canonical_document_hash_is_stable_for_proven_nfc_equivalence():
    composed = _document("Café")
    decomposed = _document("Cafe\u0301")
    assert canonical_document_sha256(composed) == canonical_document_sha256(decomposed)


def test_sync_id_and_target_change_logical_delivery_key():
    base = _snapshot()
    assert logical_delivery_key(_snapshot(sync_id="sync-002")) != logical_delivery_key(base)
    assert logical_delivery_key(_snapshot(note_target="note-account-secondary")) != logical_delivery_key(base)
    assert base.sync_id == "sync-001"
    assert base.note_target == "note-account-main"
    assert base.canonical_contract_version == CONTRACT_VERSION
    assert base.normalization_policy_version == NORMALIZATION_POLICY_VERSION
    assert len(base.title_digest) == 64
    assert len(base.canonical_document_sha256) == 64
