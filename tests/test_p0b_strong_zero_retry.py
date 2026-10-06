from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

import note_delivery_runtime as delivery_runtime
from note_delivery_ledger import (
    DeliveryState,
    SQLiteDeliveryLedger,
    build_delivery_snapshot,
)
from note_delivery_runtime import PreparedDelivery
from note_delivery_strong_zero import (
    EVIDENCE_CATEGORY_PREFIX,
    strong_zero_evidence_digest,
)
from note_document_contract import Document, Paragraph, Text
from run_p0b_strong_zero_retry import (
    StrongZeroRetryError,
    reconcile_expired_retry_intent,
    run_reconciled_retry,
)


def _snapshot(*, manuscript_sha256: str = "1" * 64):
    return build_delivery_snapshot(
        sync_id="a" * 32,
        queue_page_id="queue-page-1",
        title="Retry authority test",
        manuscript_sha256=manuscript_sha256,
        publication_policy_sha256="2" * 64,
        document=Document((Paragraph((Text("canonical body"),)),)),
        transform_versions=(("run222", "note-presentation-integrity-v1"),),
        eyecatch_sha256="3" * 64,
        eyecatch_asset_id="hero.png",
        note_target="trendhub-biz",
        ready_provenance="ready-waiting-current-publication-v1:test-contract",
    )


def _census(**overrides):
    value = {
        "status": "census_complete_no_mutation",
        "authenticated": True,
        "private_note_card_count": 5,
        "exact_target_count": 0,
        "suspicious_blank_count": 0,
        "unreadable_count": 0,
        "decision": "strong_zero",
        "zero_model_calls": True,
        "mutation_count": 0,
    }
    value.update(overrides)
    return value


def _ledger(tmp_path: Path) -> SQLiteDeliveryLedger:
    ledger = SQLiteDeliveryLedger(tmp_path / "delivery.sqlite3")
    ledger.initialize()
    return ledger


def _manual_reconciliation(ledger, snapshot, *, category=None, with_draft=False):
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
    evidence = category or (
        EVIDENCE_CATEGORY_PREFIX + strong_zero_evidence_digest(_census())
    )
    return ledger.record_blocked(
        current.operation_key,
        state=DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        category=evidence,
        expected_version=current.state_version,
    )


def _prepared(snapshot, tmp_path):
    eyecatch = tmp_path / "hero.png"
    eyecatch.write_bytes(b"png")
    return PreparedDelivery(
        MappingProxyType({"sync_id": snapshot.sync_id}),
        snapshot,
        eyecatch,
    )


def test_run_reconciled_retry_validates_fresh_evidence_before_runtime_authorization(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    snapshot = _snapshot()
    manual = _manual_reconciliation(ledger, snapshot)
    prepared = _prepared(snapshot, tmp_path)
    calls = []

    monkeypatch.setattr(delivery_runtime, "prepare_delivery", lambda _base, _sync: prepared)
    monkeypatch.setattr(
        delivery_runtime,
        "create_reconciled_retry",
        lambda base, ledger_arg, prepared_arg, **kwargs: calls.append(
            (base, ledger_arg, prepared_arg, kwargs)
        ) or manual,
    )

    result = run_reconciled_retry(
        object(),
        ledger,
        sync_id=snapshot.sync_id,
        note_target=snapshot.note_target,
        current_snapshot=snapshot,
        census=_census(),
        run_correlation_id="run-retry",
        expected_version=manual.state_version,
    )

    assert result == manual
    assert len(calls) == 1
    assert calls[0][1] is ledger
    assert calls[0][2] is prepared
    assert calls[0][3] == {
        "run_correlation_id": "run-retry",
        "expected_version": manual.state_version,
    }


@pytest.mark.parametrize(
    "case",
    ("non_strong_zero", "wrong_state", "draft_present", "snapshot_drift", "bad_evidence", "stale_version"),
)
def test_run_reconciled_retry_blocks_before_runtime_authorization(tmp_path, monkeypatch, case):
    ledger = _ledger(tmp_path)
    snapshot = _snapshot()
    census = _census()
    if case == "wrong_state":
        record = ledger.begin_or_load(snapshot, run_correlation_id="run-original").record
    elif case == "draft_present":
        record = _manual_reconciliation(ledger, snapshot, with_draft=True)
    elif case == "bad_evidence":
        record = _manual_reconciliation(
            ledger,
            snapshot,
            category="creation_absence_confirmed_strong_zero:BAD",
        )
    else:
        record = _manual_reconciliation(ledger, snapshot)

    supplied_snapshot = snapshot
    expected_version = record.state_version
    if case == "non_strong_zero":
        census = _census(decision="ambiguous")
    elif case == "snapshot_drift":
        supplied_snapshot = _snapshot(manuscript_sha256="9" * 64)
    elif case == "stale_version":
        expected_version -= 1

    monkeypatch.setattr(
        delivery_runtime,
        "create_reconciled_retry",
        lambda *_args, **_kwargs: pytest.fail("runtime authorization must not be called"),
    )
    monkeypatch.setattr(
        delivery_runtime,
        "prepare_delivery",
        lambda _base, _sync: _prepared(supplied_snapshot, tmp_path),
    )

    with pytest.raises(StrongZeroRetryError):
        run_reconciled_retry(
            object(),
            ledger,
            sync_id=snapshot.sync_id,
            note_target=snapshot.note_target,
            current_snapshot=supplied_snapshot,
            census=census,
            run_correlation_id="run-retry",
            expected_version=expected_version,
        )


def test_run_reconciled_retry_reconstructed_snapshot_must_match_before_authorization(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    snapshot = _snapshot()
    manual = _manual_reconciliation(ledger, snapshot)
    reconstructed = _snapshot(manuscript_sha256="9" * 64)
    monkeypatch.setattr(
        delivery_runtime,
        "prepare_delivery",
        lambda _base, _sync: _prepared(reconstructed, tmp_path),
    )
    monkeypatch.setattr(
        delivery_runtime,
        "create_reconciled_retry",
        lambda *_args, **_kwargs: pytest.fail("runtime authorization must not be called"),
    )

    with pytest.raises(StrongZeroRetryError, match="reconstructed snapshot"):
        run_reconciled_retry(
            object(),
            ledger,
            sync_id=snapshot.sync_id,
            note_target=snapshot.note_target,
            current_snapshot=snapshot,
            census=_census(),
            run_correlation_id="run-retry",
            expected_version=manual.state_version,
        )


def _retry_authorized(ledger, snapshot):
    manual = _manual_reconciliation(ledger, snapshot)
    decision = ledger.authorize_reconciled_retry(
        snapshot,
        run_correlation_id="run-retry",
        expected_version=manual.state_version,
    )
    assert decision.creation_authorized is True
    assert decision.record.state == DeliveryState.CREATE_INTENT_RECORDED
    return decision.record


def test_lease_expiry_alone_never_restores_creation_authority(tmp_path):
    ledger = _ledger(tmp_path)
    snapshot = _snapshot()
    retry = _retry_authorized(ledger, snapshot)
    conn = sqlite3.connect(ledger.path)
    conn.execute(
        "UPDATE deliveries SET owner_expires_at='2000-01-01T00:00:00Z' WHERE operation_key=?",
        (retry.operation_key,),
    )
    conn.commit()
    conn.close()

    ordinary = ledger.begin_or_load(snapshot, run_correlation_id="ordinary-retry")
    assert ordinary.creation_authorized is False
    assert ordinary.record.state == DeliveryState.CREATE_INTENT_RECORDED


def test_expired_retry_intent_requires_expiry_then_returns_only_to_manual_reconciliation(tmp_path):
    ledger = _ledger(tmp_path)
    snapshot = _snapshot()
    retry = _retry_authorized(ledger, snapshot)

    with pytest.raises(StrongZeroRetryError, match="lease has not expired"):
        reconcile_expired_retry_intent(
            ledger,
            sync_id=snapshot.sync_id,
            note_target=snapshot.note_target,
            current_snapshot=snapshot,
            census=_census(private_note_card_count=7),
            now=datetime(2000, 1, 1, tzinfo=timezone.utc),
        )

    fresh = _census(private_note_card_count=7)
    updated = reconcile_expired_retry_intent(
        ledger,
        sync_id=snapshot.sync_id,
        note_target=snapshot.note_target,
        current_snapshot=snapshot,
        census=fresh,
        now=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    assert updated.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED
    assert updated.state_version == retry.state_version + 1
    assert updated.draft_id is None
    assert updated.conflict_category == (
        EVIDENCE_CATEGORY_PREFIX + strong_zero_evidence_digest(fresh)
    )

    ordinary = ledger.begin_or_load(snapshot, run_correlation_id="ordinary-after-reconcile")
    assert ordinary.creation_authorized is False
    assert ordinary.record.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED


@pytest.mark.parametrize("case", ("non_strong_zero", "snapshot_drift", "draft_present", "bad_retained_evidence"))
def test_expired_retry_intent_blocks_unsafe_reconciliation(tmp_path, case):
    ledger = _ledger(tmp_path)
    snapshot = _snapshot()
    retry = _retry_authorized(ledger, snapshot)
    supplied_snapshot = snapshot
    census = _census(private_note_card_count=7)

    if case == "non_strong_zero":
        census = _census(decision="ambiguous")
    elif case == "snapshot_drift":
        supplied_snapshot = _snapshot(manuscript_sha256="9" * 64)
    elif case == "draft_present":
        retry = ledger.record_draft_created(
            retry.operation_key,
            draft_id="opaque-new-draft",
            note_host="note.com",
            expected_version=retry.state_version,
        )
    elif case == "bad_retained_evidence":
        conn = sqlite3.connect(ledger.path)
        conn.execute(
            "UPDATE deliveries SET conflict_category=? WHERE operation_key=?",
            ("creation_absence_confirmed_strong_zero:BAD", retry.operation_key),
        )
        conn.commit()
        conn.close()

    with pytest.raises(StrongZeroRetryError):
        reconcile_expired_retry_intent(
            ledger,
            sync_id=snapshot.sync_id,
            note_target=snapshot.note_target,
            current_snapshot=supplied_snapshot,
            census=census,
            now=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )

    current = ledger.get_active_by_logical_key(retry.logical_key)
    assert current is not None
    assert current.state != DeliveryState.MANUAL_RECONCILIATION_REQUIRED
