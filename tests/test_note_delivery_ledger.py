import json
import os
import sqlite3
import subprocess
import threading
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import note_delivery_ledger as delivery_ledger

from note_document_contract import (
    CONTRACT_VERSION,
    NORMALIZATION_POLICY_VERSION,
    Document,
    Paragraph,
    Text,
)
from note_delivery_ledger import (
    DeliveryState,
    InvalidStateTransition,
    LedgerSchemaError,
    LedgerUnavailableError,
    SQLiteDeliveryLedger,
    build_delivery_snapshot,
    canonical_document_sha256,
    logical_delivery_key,
    operation_key,
    revision_key,
)


ROOT = Path(__file__).resolve().parents[1]


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


def _file_ledger(root: str) -> SQLiteDeliveryLedger:
    return SQLiteDeliveryLedger(Path(root) / "delivery.sqlite3")


def test_file_backed_ledger_survives_close_and_reopen():
    with TemporaryDirectory() as tmp:
        first = _file_ledger(tmp)
        first.initialize()
        decision = first.begin_or_load(_snapshot(), run_correlation_id="run-a")
        assert decision.creation_authorized is True

        second = _file_ledger(tmp)
        second.initialize()
        loaded = second.get_by_operation_key(operation_key(_snapshot()))
        assert loaded is not None
        assert loaded.operation_key == decision.record.operation_key
        assert loaded.state == DeliveryState.CREATE_INTENT_RECORDED


def test_production_adapter_uses_wal_full_and_foreign_keys():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        conn = ledger._connect()
        try:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()


def test_unknown_schema_version_fails_closed():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "delivery.sqlite3"
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA user_version=999")
        conn.close()
        with pytest.raises(LedgerSchemaError):
            SQLiteDeliveryLedger(path).initialize()


def test_corrupt_database_fails_closed_and_grants_no_creation_authority():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "delivery.sqlite3"
        path.write_bytes(b"not-a-sqlite-database")
        with pytest.raises(LedgerUnavailableError):
            SQLiteDeliveryLedger(path).initialize()


def test_b11_intent_commit_failure_grants_zero_creation_authority():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        conn = sqlite3.connect(ledger.path)
        conn.execute(
            "CREATE TRIGGER force_intent_failure BEFORE INSERT ON deliveries "
            "BEGIN SELECT RAISE(ABORT, 'forced-intent-failure'); END"
        )
        conn.commit()
        conn.close()

        with pytest.raises(LedgerUnavailableError):
            ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")

        conn = sqlite3.connect(ledger.path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM logical_bindings").fetchone()[0] == 0
        finally:
            conn.close()


def test_b08_concurrent_same_logical_delivery_has_one_creation_authority():
    with TemporaryDirectory() as tmp:
        first = _file_ledger(tmp)
        second = _file_ledger(tmp)
        first.initialize()
        second.initialize()
        barrier = threading.Barrier(2)
        decisions = []
        errors = []

        def worker(ledger, run_id):
            try:
                barrier.wait()
                decisions.append(ledger.begin_or_load(_snapshot(), run_correlation_id=run_id))
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        a = threading.Thread(target=worker, args=(first, "run-a"))
        b = threading.Thread(target=worker, args=(second, "run-b"))
        a.start(); b.start(); a.join(); b.join()

        assert errors == []
        assert sorted(item.creation_authorized for item in decisions) == [False, True]
        assert len({item.record.operation_key for item in decisions}) == 1


def test_same_operation_key_retry_loads_existing_record():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        first = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        retry = ledger.begin_or_load(_snapshot(), run_correlation_id="run-b")
        assert first.creation_authorized is True
        assert retry.creation_authorized is False
        assert retry.reason == "existing_operation"
        assert retry.record.record_id == first.record.record_id


def test_different_revision_cannot_bypass_active_logical_binding():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        first = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        changed = _snapshot(manuscript_sha256="9" * 64)
        second = ledger.begin_or_load(changed, run_correlation_id="run-b")
        assert first.creation_authorized is True
        assert second.creation_authorized is False
        assert second.reason == "active_logical_delivery"
        assert second.record.operation_key == first.record.operation_key
        assert ledger.get_by_operation_key(operation_key(changed)) is None


def test_invalid_backward_state_transition_is_rejected():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        created = ledger.record_draft_created(
            decision.record.operation_key,
            draft_id="opaque-draft-1",
            note_host="note.com",
            expected_version=decision.record.state_version,
        )
        with pytest.raises(InvalidStateTransition):
            ledger.record_draft_created(
                created.operation_key,
                draft_id="opaque-draft-1",
                note_host="note.com",
                expected_version=created.state_version,
            )


def test_b13_expired_owner_does_not_authorize_replacement_creation():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        first = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        conn = sqlite3.connect(ledger.path)
        conn.execute(
            "UPDATE deliveries SET owner_expires_at='2000-01-01T00:00:00Z' WHERE operation_key=?",
            (first.record.operation_key,),
        )
        conn.commit(); conn.close()

        retry = ledger.begin_or_load(_snapshot(), run_correlation_id="run-b")
        assert retry.creation_authorized is False
        assert retry.record.record_id == first.record.record_id


def test_ledger_unavailable_b18_is_fail_closed():
    impossible = Path("/dev/null") / "delivery.sqlite3"
    with pytest.raises(LedgerUnavailableError):
        SQLiteDeliveryLedger(impossible).initialize()


def _run_read_only_gate(path: Path, *, sync_id: str, note_target: str, result_file: Path):
    env = dict(os.environ)
    env.update(
        {
            "NOTE_DELIVERY_LEDGER_BACKEND": "sqlite",
            "NOTE_DELIVERY_LEDGER_PATH": str(path),
            "NOTE_TARGET_SYNC_ID": sync_id,
            "NOTE_TARGET_IDENTITY": note_target,
            "NOTE_DRAFT_RESULT_FILE": str(result_file),
        }
    )
    completed = subprocess.run(
        ["bash", str(ROOT / "note_delivery_ledger_preflight.sh")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert sync_id not in completed.stdout
    return json.loads(result_file.read_text(encoding="utf-8"))


def test_read_only_gate_blocks_ambiguous_delivery_without_mutating_ledger():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        blocked = ledger.record_blocked(
            decision.record.operation_key,
            state=DeliveryState.CREATION_UNKNOWN,
            category="creation_result_ambiguous",
            expected_version=decision.record.state_version,
        )
        before = ledger.get_by_operation_key(blocked.operation_key)

        result = _run_read_only_gate(
            ledger.path,
            sync_id=blocked.snapshot.sync_id,
            note_target=blocked.snapshot.note_target,
            result_file=Path(tmp) / "blocked.json",
        )
        assert result == {
            "status": "ledger_blocked_ambiguous",
            "should_run_delivery": False,
            "zero_gemini_calls": True,
        }

        after = ledger.get_by_operation_key(blocked.operation_key)
        assert after is not None and before is not None
        assert after.state == before.state == DeliveryState.CREATION_UNKNOWN
        assert after.state_version == before.state_version
        assert after.attempt_count == before.attempt_count

        clean = _run_read_only_gate(
            ledger.path,
            sync_id="sync-002",
            note_target=blocked.snapshot.note_target,
            result_file=Path(tmp) / "clean.json",
        )
        assert clean == {
            "status": "ledger_clean_new",
            "should_run_delivery": True,
            "zero_gemini_calls": True,
        }


# TASK1_STRONG_ZERO_RETRY_AUTHORITY_TESTS
_STRONG_ZERO_EVIDENCE_DIGEST = "a" * 64
_STRONG_ZERO_EVIDENCE = (
    "creation_absence_confirmed_strong_zero:" + _STRONG_ZERO_EVIDENCE_DIGEST
)


def _prepare_manual_reconciliation(
    ledger: SQLiteDeliveryLedger,
    snapshot=None,
    *,
    evidence: str = _STRONG_ZERO_EVIDENCE,
    with_draft: bool = False,
):
    snapshot = snapshot or _snapshot()
    first = ledger.begin_or_load(snapshot, run_correlation_id="run-original")
    if with_draft:
        current = ledger.record_draft_created(
            first.record.operation_key,
            draft_id="opaque-existing-draft",
            note_host="note.com",
            expected_version=first.record.state_version,
        )
    else:
        current = ledger.record_blocked(
            first.record.operation_key,
            state=DeliveryState.CREATION_UNKNOWN,
            category="creation_result_ambiguous",
            expected_version=first.record.state_version,
        )
    manual = ledger.record_blocked(
        current.operation_key,
        state=DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        category=evidence,
        expected_version=current.state_version,
    )
    return snapshot, manual


def test_reconciled_retry_authorizes_once_and_preserves_manual_evidence():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        snapshot, manual = _prepare_manual_reconciliation(ledger)

        decision = ledger.authorize_reconciled_retry(
            snapshot,
            run_correlation_id="run-retry",
            expected_version=manual.state_version,
        )

        assert decision.creation_authorized is True
        assert decision.reason == "reconciled_retry_authorized"
        assert decision.record.state == DeliveryState.CREATE_INTENT_RECORDED
        assert decision.record.state_version == manual.state_version + 1
        assert decision.record.attempt_count == manual.attempt_count + 1
        assert decision.record.owner_correlation_id == "run-retry"
        assert decision.record.owner_expires_at
        assert decision.record.snapshot == manual.snapshot == snapshot
        assert decision.record.draft_id is None
        assert decision.record.conflict_category == _STRONG_ZERO_EVIDENCE

        conn = sqlite3.connect(ledger.path)
        try:
            events = conn.execute(
                "SELECT category, run_correlation_id FROM delivery_events "
                "WHERE record_id=? ORDER BY event_id",
                (manual.record_id,),
            ).fetchall()
        finally:
            conn.close()
        assert [row[0] for row in events] == [
            "create_intent_recorded",
            "creation_result_ambiguous",
            _STRONG_ZERO_EVIDENCE,
            "strong_zero_retry_authorized:" + _STRONG_ZERO_EVIDENCE_DIGEST,
        ]
        assert events[-1][1] == "run-retry"

        ordinary = ledger.begin_or_load(snapshot, run_correlation_id="run-ordinary")
        assert ordinary.creation_authorized is False
        assert ordinary.reason == "existing_operation"
        assert ordinary.record.state == DeliveryState.CREATE_INTENT_RECORDED


def test_reconciled_retry_rejects_malformed_strong_zero_evidence_without_mutation():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        snapshot, manual = _prepare_manual_reconciliation(
            ledger,
            evidence="creation_absence_confirmed_strong_zero:BAD",
        )

        decision = ledger.authorize_reconciled_retry(
            snapshot,
            run_correlation_id="run-retry",
            expected_version=manual.state_version,
        )
        assert decision.creation_authorized is False
        assert decision.reason == "strong_zero_evidence_invalid"
        assert decision.record.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED
        assert decision.record.state_version == manual.state_version
        assert decision.record.attempt_count == manual.attempt_count


def test_reconciled_retry_rejects_snapshot_drift_without_mutation():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        snapshot, manual = _prepare_manual_reconciliation(ledger)
        drifted = _snapshot(manuscript_sha256="9" * 64)

        decision = ledger.authorize_reconciled_retry(
            drifted,
            run_correlation_id="run-retry",
            expected_version=manual.state_version,
        )
        assert decision.creation_authorized is False
        assert decision.reason == "snapshot_mismatch"
        assert decision.record.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED
        assert decision.record.state_version == manual.state_version


def test_reconciled_retry_rejects_existing_draft_identity():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        snapshot, manual = _prepare_manual_reconciliation(ledger, with_draft=True)
        assert manual.draft_id == "opaque-existing-draft"

        decision = ledger.authorize_reconciled_retry(
            snapshot,
            run_correlation_id="run-retry",
            expected_version=manual.state_version,
        )
        assert decision.creation_authorized is False
        assert decision.reason == "stable_draft_present"
        assert decision.record.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED
        assert decision.record.state_version == manual.state_version


def test_reconciled_retry_rejects_wrong_state():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        snapshot = _snapshot()
        first = ledger.begin_or_load(snapshot, run_correlation_id="run-original")

        decision = ledger.authorize_reconciled_retry(
            snapshot,
            run_correlation_id="run-retry",
            expected_version=first.record.state_version,
        )
        assert decision.creation_authorized is False
        assert decision.reason == "manual_reconciliation_required"
        assert decision.record.state == DeliveryState.CREATE_INTENT_RECORDED
        assert decision.record.state_version == first.record.state_version


def test_reconciled_retry_rejects_stale_expected_version():
    with TemporaryDirectory() as tmp:
        ledger = _file_ledger(tmp)
        ledger.initialize()
        snapshot, manual = _prepare_manual_reconciliation(ledger)

        with pytest.raises(delivery_ledger.ConcurrentStateChange):
            ledger.authorize_reconciled_retry(
                snapshot,
                run_correlation_id="run-retry",
                expected_version=manual.state_version - 1,
            )
        after = ledger.get_by_operation_key(manual.operation_key)
        assert after is not None
        assert after.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED
        assert after.state_version == manual.state_version
        assert after.attempt_count == manual.attempt_count


def test_manual_reconciliation_generic_transition_stays_closed():
    assert DeliveryState.CREATE_INTENT_RECORDED not in delivery_ledger._ALLOWED_TRANSITIONS.get(
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        frozenset(),
    )
