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
        "rejection_counts": {bucket: 0 for bucket in recovery.REJECTION_BUCKETS},
        "inspection_stage_counts": {stage: 0 for stage in recovery.INSPECTION_STAGES},
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


def test_non_unique_readonly_audit_reports_counts_without_authorizing_recovery(monkeypatch):
    import types
    recovery = _module()
    monkeypatch.setattr(recovery, "SQLiteDeliveryLedger", lambda _: object())
    monkeypatch.setattr(recovery, "require_creation_unknown_record", lambda *a, **kw: object())
    monkeypatch.setattr(
        recovery, "_expected_prepared_delivery",
        lambda _: types.SimpleNamespace(article={"title": "private", "manuscript": "body"}),
    )

    for matches, expected in (
        ([], "recovery_no_verified_match"),
        ([{"draft_id": "opaque-one"}, {"draft_id": "opaque-two"}],
         "recovery_multiple_verified_matches"),
    ):
        monkeypatch.setattr(
            recovery, "_discover_verified_matches",
            lambda article, record, matches=matches: (
                matches, 6,
                {"different_title": 6 - len(matches)},
                {"title_read": 1},
            ),
        )
        result = recovery.run(
            confirm=recovery.CONFIRM_TOKEN, sync_id="a" * 32,
            note_target="trendhub_biz", ledger_path="/unused/read-only/ledger",
        )
        assert result["status"] == expected
        assert result["match_count"] == len(matches)
        assert result["history_candidate_count"] == 6
        assert result["rejection_counts"]["different_title"] == 6 - len(matches)
        assert result["inspection_stage_counts"]["title_read"] == 1
        assert result["read_only"] is True
        assert result["draft_mutation"] is False
        assert result["public_release"] is False
        assert "recovered_draft_id" not in result


def test_cli_writes_safe_blocked_result_then_returns_failure(tmp_path, monkeypatch, capsys):
    import json
    import sys
    recovery = _module()
    blocked = {
        "status": "recovery_no_verified_match",
        "read_only": True, "zero_gemini_calls": True,
        "draft_mutation": False, "public_release": False,
        "match_count": 0, "history_candidate_count": 9,
        "editor_route_hash": "",
        "rejection_counts": {"different_title": 9},
    }
    monkeypatch.setattr(recovery, "run", lambda **kwargs: dict(blocked))
    target = tmp_path / "read-only-result.json"
    monkeypatch.setattr(sys, "argv", ["audit", "--result-file", str(target)])
    with pytest.raises(recovery.CreationRecoveryAuditError):
        recovery.main()
    assert json.loads(target.read_text(encoding="utf-8")) == blocked
    output = capsys.readouterr().out
    assert '"match_count": 0' in output
    assert '"history_candidate_count": 9' in output
    assert "draft_id" not in output


def test_rejection_diagnostics_are_fixed_bucket_counts_without_private_identity():
    recovery = _module()
    unsafe = {
        "status": "recovery_no_verified_match",
        "rejection_counts": {
            "different_title": 16,
            "logged_out": 2,
            "inspection_error": 6,
            "candidate_private_url": "https://note.com/notes/secret/edit",
            "secret_manuscript": "private text",
        },
        "recovered_draft_id": "secret",
    }
    safe = recovery.safe_recovery_projection(unsafe)
    assert safe["rejection_counts"] == {
        "logged_out": 2, "non_editor": 0, "different_title": 16,
        "content_or_eyecatch": 0, "canonical_hash": 0,
        "inspection_error": 6,
    }
    assert "candidate_private_url" not in str(safe)
    assert "secret_manuscript" not in str(safe)
    assert "recovered_draft_id" not in str(safe)


def test_failed_recovery_still_requires_exact_one_verified_match():
    recovery = _module()
    assert "recovery_no_verified_match" in inspect.getsource(recovery.run)
    assert "recovery_multiple_verified_matches" in inspect.getsource(recovery.run)
    assert "len(matches) != 1" in inspect.getsource(recovery.run)


def test_inspection_stage_projection_is_fixed_and_never_leaks_raw_browser_data():
    recovery = _module()
    safe = recovery.safe_recovery_projection({
        "status": "recovery_no_verified_match",
        "inspection_stage_counts": {
            "title_read": 5, "navigation": 1,
            "private_editor_url": "https://note.com/notes/secret/edit",
            "raw_browser_error": "Private title is secret",
        },
    })
    assert safe["inspection_stage_counts"]["title_read"] == 5
    assert safe["inspection_stage_counts"]["navigation"] == 1
    assert set(safe["inspection_stage_counts"]) == set(recovery.INSPECTION_STAGES)
    assert "private_editor_url" not in str(safe)
    assert "raw_browser_error" not in str(safe)
    assert "secret" not in str(safe).lower()
