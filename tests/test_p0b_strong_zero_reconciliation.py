from __future__ import annotations

import importlib
import importlib.util
import inspect
import tempfile
from pathlib import Path

import pytest

from note_delivery_ledger import DeliveryState, SQLiteDeliveryLedger, build_delivery_snapshot
from note_document_contract import Document, Paragraph, Text


def _module():
    spec = importlib.util.find_spec("run_p0b_strong_zero_reconciliation")
    assert spec is not None, "strong-zero reconciliation module must exist"
    return importlib.import_module("run_p0b_strong_zero_reconciliation")


def _snapshot():
    return build_delivery_snapshot(
        sync_id="a" * 32,
        queue_page_id="queue-page",
        title="Strong zero recovery target",
        manuscript_sha256="1" * 64,
        publication_policy_sha256="2" * 64,
        document=Document((Paragraph((Text("canonical body"),)),)),
        transform_versions=(("run222", "note-presentation-integrity-v1"),),
        eyecatch_sha256="3" * 64,
        eyecatch_asset_id="asset-id",
        note_target="trendhub_biz",
        ready_provenance="ready-waiting-current-publication-v1:test",
    )


def _strong_zero():
    return {
        "status": "census_complete_no_mutation",
        "authenticated": True,
        "private_note_card_count": 1,
        "exact_target_count": 0,
        "suspicious_blank_count": 0,
        "unreadable_count": 0,
        "decision": "strong_zero",
        "zero_model_calls": True,
        "mutation_count": 0,
    }


def _ambiguous_ledger(tmp: str):
    ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
    ledger.initialize()
    decision = ledger.begin_or_load(_snapshot(), run_correlation_id="b01-failed")
    ambiguous = ledger.record_blocked(
        decision.record.operation_key,
        state=DeliveryState.CREATION_UNKNOWN,
        category="creation_result_ambiguous",
        expected_version=decision.record.state_version,
    )
    return ledger, ambiguous


def test_strong_zero_reconciliation_is_two_phase_and_does_not_reauthorize_creation():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger, ambiguous = _ambiguous_ledger(tmp)
        result = recovery.reconcile_strong_zero(
            ledger,
            sync_id="a" * 32,
            note_target="trendhub_biz",
            census=_strong_zero(),
        )

        current = ledger.get_active_by_logical_key(ambiguous.logical_key)
        assert current is not None
        assert current.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED
        assert current.state_version == ambiguous.state_version + 1
        assert current.draft_id is None
        assert str(current.conflict_category or "").startswith(
            "creation_absence_confirmed_strong_zero:"
        )
        digest = str(current.conflict_category).split(":", 1)[1]
        assert len(digest) == 64
        assert all(ch in "0123456789abcdef" for ch in digest)

        assert result == {
            "status": "strong_zero_reconciled_no_create_authority",
            "prior_state": DeliveryState.CREATION_UNKNOWN.value,
            "state": DeliveryState.MANUAL_RECONCILIATION_REQUIRED.value,
            "state_version": current.state_version,
            "creation_authorized": False,
            "note_mutation_count": 0,
            "zero_model_calls": True,
            "public_release": False,
            "evidence_digest": digest,
        }

        retry = ledger.begin_or_load(_snapshot(), run_correlation_id="must-not-create")
        assert retry.creation_authorized is False
        assert retry.record.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED


def test_reconciliation_rejects_any_census_that_is_not_strict_strong_zero():
    recovery = _module()
    invalid = []
    for key, value in (
        ("decision", "ambiguous"),
        ("authenticated", False),
        ("private_note_card_count", 0),
        ("exact_target_count", 1),
        ("suspicious_blank_count", 1),
        ("unreadable_count", 1),
        ("zero_model_calls", False),
        ("mutation_count", 1),
    ):
        item = _strong_zero()
        item[key] = value
        invalid.append(item)

    with tempfile.TemporaryDirectory() as tmp:
        ledger, ambiguous = _ambiguous_ledger(tmp)
        for census in invalid:
            with pytest.raises(recovery.StrongZeroReconciliationError):
                recovery.reconcile_strong_zero(
                    ledger,
                    sync_id="a" * 32,
                    note_target="trendhub_biz",
                    census=census,
                )
            current = ledger.get_active_by_logical_key(ambiguous.logical_key)
            assert current is not None
            assert current.state == DeliveryState.CREATION_UNKNOWN


def test_reconciliation_requires_exact_ambiguous_identity_and_is_not_repeatable():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger, ambiguous = _ambiguous_ledger(tmp)
        with pytest.raises(recovery.StrongZeroReconciliationError):
            recovery.reconcile_strong_zero(
                ledger,
                sync_id="b" * 32,
                note_target="trendhub_biz",
                census=_strong_zero(),
            )
        current = ledger.get_active_by_logical_key(ambiguous.logical_key)
        assert current is not None
        assert current.state == DeliveryState.CREATION_UNKNOWN

        recovery.reconcile_strong_zero(
            ledger,
            sync_id="a" * 32,
            note_target="trendhub_biz",
            census=_strong_zero(),
        )
        with pytest.raises(recovery.StrongZeroReconciliationError):
            recovery.reconcile_strong_zero(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub_biz",
                census=_strong_zero(),
            )


def test_reconciliation_module_has_no_note_or_queue_mutation_or_creation_path():
    recovery = _module()
    source = inspect.getsource(recovery)
    required = (
        "get_active_by_logical_key(",
        "record_blocked(",
        "DeliveryState.MANUAL_RECONCILIATION_REQUIRED",
    )
    for token in required:
        assert token in source

    forbidden = (
        "begin_or_load(",
        "_create_browser_draft(",
        "record_draft_created(",
        "record_verified(",
        "record_queue_confirmed(",
        "patch_and_readback_draft_binding(",
        "requests.post(",
        ".click(",
        ".fill(",
        "keyboard.press",
        "keyboard.insert_text",
    )
    for token in forbidden:
        assert token not in source
