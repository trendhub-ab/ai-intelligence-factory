from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from note_delivery_ledger import (
    DeliveryState,
    SQLiteDeliveryLedger,
    build_delivery_snapshot,
)
from note_delivery_runtime import InplaceUpdateBlocked, require_inplace_update_allowed
from note_document_contract import parse_presentation_markdown


def _snapshot(*, manuscript_sha256="1" * 64):
    return build_delivery_snapshot(
        sync_id="a" * 32,
        queue_page_id="queue-page-1",
        title="Public title",
        manuscript_sha256=manuscript_sha256,
        publication_policy_sha256="2" * 64,
        document=parse_presentation_markdown("Body"),
        transform_versions=(("run222", "note-presentation-integrity-v1"),),
        eyecatch_sha256="3" * 64,
        eyecatch_asset_id="hero.png",
        note_target="trendhub-biz",
        ready_provenance="ready-waiting-current-publication-v1:contract",
    )


def _verified_ledger(tmp: str):
    ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
    decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
    created = ledger.record_draft_created(
        decision.record.operation_key,
        draft_id="opaque_draft_1",
        note_host="note.com",
        expected_version=decision.record.state_version,
    )
    verified = ledger.record_verified(
        decision.record.operation_key,
        canonical_sha256=created.snapshot.canonical_document_sha256,
        expected_version=created.state_version,
    )
    return ledger, verified


def test_exact_bound_private_draft_with_unchanged_hash_may_enter_explicit_update_path():
    with TemporaryDirectory() as tmp:
        ledger, verified = _verified_ledger(tmp)
        allowed = require_inplace_update_allowed(
            ledger,
            sync_id="a" * 32,
            note_target="trendhub-biz",
            draft_id="opaque_draft_1",
            current_canonical_sha256=verified.last_verified_canonical_hash,
            private_state=True,
            account_matches=True,
        )
        assert allowed.operation_key == verified.operation_key


def test_human_edit_hash_drift_blocks_before_paste():
    with TemporaryDirectory() as tmp:
        ledger, _ = _verified_ledger(tmp)
        with pytest.raises(InplaceUpdateBlocked, match="human_edit_detected"):
            require_inplace_update_allowed(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub-biz",
                draft_id="opaque_draft_1",
                current_canonical_sha256="9" * 64,
                private_state=True,
                account_matches=True,
            )


def test_b14_foreign_account_or_wrong_bound_draft_is_rejected():
    with TemporaryDirectory() as tmp:
        ledger, verified = _verified_ledger(tmp)
        with pytest.raises(InplaceUpdateBlocked, match="bound_draft_foreign"):
            require_inplace_update_allowed(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub-biz",
                draft_id="opaque_draft_1",
                current_canonical_sha256=verified.last_verified_canonical_hash,
                private_state=True,
                account_matches=False,
            )
        with pytest.raises(InplaceUpdateBlocked, match="bound_draft_identity_mismatch"):
            require_inplace_update_allowed(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub-biz",
                draft_id="other_draft",
                current_canonical_sha256=verified.last_verified_canonical_hash,
                private_state=True,
                account_matches=True,
            )


def test_b15_nonprivate_bound_draft_is_blocked():
    with TemporaryDirectory() as tmp:
        ledger, verified = _verified_ledger(tmp)
        with pytest.raises(InplaceUpdateBlocked, match="bound_draft_not_private"):
            require_inplace_update_allowed(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub-biz",
                draft_id="opaque_draft_1",
                current_canonical_sha256=verified.last_verified_canonical_hash,
                private_state=False,
                account_matches=True,
            )


def test_missing_preledger_binding_requires_manual_reconciliation():
    with TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        ledger.initialize()
        with pytest.raises(InplaceUpdateBlocked, match="preledger_binding_requires_manual_reconciliation"):
            require_inplace_update_allowed(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub-biz",
                draft_id="opaque_draft_1",
                current_canonical_sha256="4" * 64,
                private_state=True,
                account_matches=True,
            )


def test_b10_new_revision_never_obtains_new_creation_authority_while_binding_is_active():
    with TemporaryDirectory() as tmp:
        ledger, verified = _verified_ledger(tmp)
        changed = replace(_snapshot(), manuscript_sha256="9" * 64)
        decision = ledger.begin_or_load(changed, run_correlation_id="run-b")
        assert decision.creation_authorized is False
        assert decision.record.operation_key == verified.operation_key
        assert decision.record.state == DeliveryState.DRAFT_VERIFIED
