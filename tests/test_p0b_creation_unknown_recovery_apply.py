from __future__ import annotations

import importlib
import tempfile
from pathlib import Path

import pytest

from note_delivery_ledger import DeliveryState, SQLiteDeliveryLedger, build_delivery_snapshot
from note_document_contract import Document, Paragraph, Text


def _module():
    return importlib.import_module("note_delivery_creation_recovery_apply")


def _snapshot(sync_id: str = "a" * 32, note_target: str = "trendhub_biz"):
    return build_delivery_snapshot(
        sync_id=sync_id,
        queue_page_id="queue-page",
        title="Private recovery target",
        manuscript_sha256="1" * 64,
        publication_policy_sha256="2" * 64,
        document=Document((Paragraph((Text("canonical body"),)),)),
        transform_versions=(("run222", "note-presentation-integrity-v1"),),
        eyecatch_sha256="3" * 64,
        eyecatch_asset_id="asset-id",
        note_target=note_target,
        ready_provenance="ready-waiting-current-publication-v1:test",
    )


def _ambiguous(ledger: SQLiteDeliveryLedger):
    decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
    return ledger.record_blocked(
        decision.record.operation_key,
        state=DeliveryState.CREATION_UNKNOWN,
        category="creation_result_ambiguous",
        expected_version=decision.record.state_version,
    )


def test_apply_verified_recovery_binds_existing_draft_without_creating_another(monkeypatch):
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
        ledger.initialize()
        ambiguous = _ambiguous(ledger)
        observed = {}

        def fake_reconcile(base, actual_ledger, verified):
            observed["state"] = verified.state
            observed["draft_id"] = verified.draft_id
            observed["canonical"] = verified.last_verified_canonical_hash
            assert actual_ledger is ledger
            return verified

        monkeypatch.setattr(recovery.delivery_runtime, "_reconcile_queue_projection", fake_reconcile)
        result = recovery.apply_verified_recovery(
            object(),
            ledger,
            ambiguous,
            {
                "draft_id": "opaque-existing-draft",
                "note_host": "editor.note.com",
                "editor_route_hash": "route-hash",
            },
        )

        assert result.state == DeliveryState.DRAFT_VERIFIED
        assert observed == {
            "state": DeliveryState.DRAFT_VERIFIED,
            "draft_id": "opaque-existing-draft",
            "canonical": ambiguous.snapshot.canonical_document_sha256,
        }
        loaded = ledger.get_by_operation_key(ambiguous.operation_key)
        assert loaded is not None
        assert loaded.state == DeliveryState.DRAFT_VERIFIED
        assert loaded.draft_id == "opaque-existing-draft"
        assert loaded.note_host == "editor.note.com"
        assert loaded.last_verified_canonical_hash == ambiguous.snapshot.canonical_document_sha256


def test_apply_verified_recovery_fails_closed_without_exact_creation_unknown_or_identity():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
        ledger.initialize()
        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")

        for record, match in (
            (decision.record, {"draft_id": "opaque", "note_host": "editor.note.com"}),
            (_ambiguous(SQLiteDeliveryLedger(Path(tmp) / "second.sqlite3")), {"draft_id": "", "note_host": "editor.note.com"}),
        ):
            with pytest.raises(recovery.CreationRecoveryApplyError):
                recovery.apply_verified_recovery(object(), ledger, record, match)


def test_apply_module_has_no_note_create_or_public_release_path():
    recovery = _module()
    source = Path(recovery.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "_create_browser_draft(",
        "CREATE_NOTE_DRAFT",
        "publish",
        "public_release=True",
    ):
        assert forbidden not in source
