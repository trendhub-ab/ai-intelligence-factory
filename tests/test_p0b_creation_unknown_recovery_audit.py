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
    spec = importlib.util.find_spec("note_delivery_creation_recovery")
    assert spec is not None, "note_delivery_creation_recovery must exist before ambiguous draft recovery can run"
    return importlib.import_module("note_delivery_creation_recovery")


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


def test_safe_projection_excludes_private_identity_and_unpublished_content():
    recovery = _module()
    full = {
        "status": "recovery_candidate_found",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "match_count": 1,
        "history_candidate_count": 7,
        "editor_route_hash": "abcdef123456",
        "recovered_draft_id": "private-draft-id",
        "sync_id": "a" * 32,
        "draft_url": "https://note.com/notes/private-draft-id/edit",
        "title": "secret unpublished title",
        "manuscript": "secret unpublished body",
    }
    safe = recovery.safe_recovery_projection(full)
    assert safe == {
        "status": "recovery_candidate_found",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "match_count": 1,
        "history_candidate_count": 7,
        "editor_route_hash": "abcdef123456",
    }
    for forbidden in ("recovered_draft_id", "sync_id", "draft_url", "title", "manuscript"):
        assert forbidden not in safe


def test_recovery_requires_existing_creation_unknown_without_draft_identity():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
        ledger.initialize()
        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        ambiguous = ledger.record_blocked(
            decision.record.operation_key,
            state=DeliveryState.CREATION_UNKNOWN,
            category="creation_result_ambiguous",
            expected_version=decision.record.state_version,
        )

        loaded = recovery.require_creation_unknown_record(
            ledger,
            sync_id="a" * 32,
            note_target="trendhub_biz",
        )
        assert loaded.record_id == ambiguous.record_id
        assert loaded.state == DeliveryState.CREATION_UNKNOWN
        assert loaded.draft_id is None


def test_recovery_rejects_missing_or_non_ambiguous_delivery():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
        ledger.initialize()
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_creation_unknown_record(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub_biz",
            )

        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_creation_unknown_record(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub_biz",
            )
        assert decision.record.state == DeliveryState.CREATE_INTENT_RECORDED


def test_recovery_candidate_selection_is_exactly_one_or_fail_closed():
    recovery = _module()
    one = recovery.require_unique_recovery_match([
        {"draft_id": "opaque-1", "editor_route_hash": "hash-1"}
    ])
    assert one["draft_id"] == "opaque-1"

    for matches in ([], [{"draft_id": "a"}, {"draft_id": "b"}]):
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_unique_recovery_match(matches)


def test_recovery_module_is_read_only_and_reuses_current_contract_verification():
    recovery = _module()
    source = inspect.getsource(recovery)
    assert "run194_note_current_contract" in source
    assert "run291_note_private_draft_audit" in source
    assert "_recent_private_edit_urls" in source
    forbidden = (
        "_create_browser_draft(",
        "_mark_draft_created(",
        "record_draft_created(",
        "record_verified(",
        "record_queue_confirmed(",
        "patch_and_readback_draft_binding(",
        ".click(",
        ".fill(",
        "keyboard.press",
        "keyboard.insert_text",
        "page.screenshot(",
        "requests.post(",
    )
    for token in forbidden:
        assert token not in source


def test_recovery_requires_immutable_snapshot_and_lossless_canonical_dom_evidence():
    recovery = _module()
    source = inspect.getsource(recovery)

    # The ambiguous attempt itself, not merely the current mutable queue projection,
    # remains the authority for which revision may be recovered.
    assert "delivery_runtime.prepare_delivery(" in source
    assert ".snapshot != record.snapshot" in source

    # A title/prefix/length heuristic is insufficient to recover external identity.
    # Candidate body must survive the same semantic DOM -> canonical document path as P0-A
    # and hash exactly to the immutable snapshot recorded before the ambiguous create.
    assert "snapshot_note_body(" in source
    assert "document_from_note_snapshot(" in source
    assert "NOTE_LIST_ITEM_PARAGRAPH_WRAPPER" in source
    assert "NOTE_BLOCKQUOTE_FIGURE_WRAPPER" in source
    assert "canonical_document_sha256(" in source
    assert "record.snapshot.canonical_document_sha256" in source
