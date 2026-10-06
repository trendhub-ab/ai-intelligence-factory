import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import note_delivery_runtime as delivery_runtime
import note_publication_reconcile as reconcile
from note_delivery_ledger import (
    ConcurrentStateChange,
    DeliveryState,
    LedgerUnavailableError,
    SQLiteDeliveryLedger,
    logical_delivery_key,
)
from note_delivery_runtime import (
    create_or_resume_delivery,
    prepare_delivery,
    revalidate_before_mutation,
)


class FakeBase:
    class NoteDraftError(RuntimeError):
        pass

    def __init__(self, article, image_bytes=b"png-v1"):
        self.article = dict(article)
        self.image_bytes = image_bytes
        self.prepare_calls = []
        self.download_calls = []
        self.note_mutations = 0
        self.tmpdir = ""

    def _prepare_article(self, requested_sync_id=""):
        self.prepare_calls.append(requested_sync_id)
        return dict(self.article)

    def _download_eyecatch(self, url, sync_id, public_title):
        self.download_calls.append((url, sync_id, public_title))
        path = Path(self.tmpdir) / f"{sync_id}-{len(self.download_calls)}.png"
        path.write_bytes(self.image_bytes)
        return path


def _article(**overrides):
    values = {
        "sync_id": "a" * 32,
        "destination_page_id": "queue-page-1",
        "title": "Public title",
        "manuscript": "Body after Run222 presentation transform",
        "manuscript_sha256": "1" * 64,
        "publication_policy_sha256": "2" * 64,
        "publication_contract": "current-contract-v1",
        "eyecatch_url": "https://cdn.example/hero__ecv1_token.png",
    }
    values.update(overrides)
    return values


def _base(tmp, **overrides):
    base = FakeBase(_article(**overrides))
    base.tmpdir = tmp
    return base


def _prepared(monkeypatch, tmp):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    base = _base(tmp)
    return base, prepare_delivery(base, "a" * 32)


def test_snapshot_is_built_after_run222_presentation_transform(monkeypatch):
    with TemporaryDirectory() as tmp:
        base, prepared = _prepared(monkeypatch, tmp)
        assert prepared.article["manuscript"] == "Body after Run222 presentation transform"
        assert ("run222", "note-presentation-integrity-v1") in prepared.snapshot.transform_versions
        assert prepared.snapshot.canonical_document_sha256
        assert prepared.snapshot.eyecatch_sha256
        assert prepared.snapshot.note_target == "trendhub-biz"
        assert base.note_mutations == 0


def test_b16_manuscript_change_blocks_before_note_mutation(monkeypatch):
    with TemporaryDirectory() as tmp:
        base, prepared = _prepared(monkeypatch, tmp)
        base.article["manuscript"] = "Different transformed body"
        with pytest.raises(base.NoteDraftError):
            revalidate_before_mutation(base, prepared)
        assert base.note_mutations == 0


def test_b16_policy_change_blocks_before_note_mutation(monkeypatch):
    with TemporaryDirectory() as tmp:
        base, prepared = _prepared(monkeypatch, tmp)
        base.article["publication_policy_sha256"] = "9" * 64
        with pytest.raises(base.NoteDraftError):
            revalidate_before_mutation(base, prepared)
        assert base.note_mutations == 0


def test_b16_title_change_blocks_before_note_mutation(monkeypatch):
    with TemporaryDirectory() as tmp:
        base, prepared = _prepared(monkeypatch, tmp)
        base.article["title"] = "Changed title"
        with pytest.raises(base.NoteDraftError):
            revalidate_before_mutation(base, prepared)
        assert base.note_mutations == 0


def test_b16_eyecatch_identity_change_blocks_before_note_mutation(monkeypatch):
    with TemporaryDirectory() as tmp:
        base, prepared = _prepared(monkeypatch, tmp)
        base.article["eyecatch_url"] = "https://cdn.example/other__ecv1_token.png"
        with pytest.raises(base.NoteDraftError):
            revalidate_before_mutation(base, prepared)
        assert base.note_mutations == 0


def test_b16_eyecatch_bytes_change_blocks_before_note_mutation(monkeypatch):
    with TemporaryDirectory() as tmp:
        base, prepared = _prepared(monkeypatch, tmp)
        base.image_bytes = b"png-v2"
        with pytest.raises(base.NoteDraftError):
            revalidate_before_mutation(base, prepared)
        assert base.note_mutations == 0


def test_queue_page_or_ready_eligibility_change_blocks_before_note_mutation(monkeypatch):
    with TemporaryDirectory() as tmp:
        base, prepared = _prepared(monkeypatch, tmp)
        base.article["destination_page_id"] = "queue-page-2"
        with pytest.raises(base.NoteDraftError):
            revalidate_before_mutation(base, prepared)
        assert base.note_mutations == 0

    with TemporaryDirectory() as tmp:
        base, prepared = _prepared(monkeypatch, tmp)

        def gone(_requested=""):
            raise base.NoteDraftError("Requested sync_id is not exactly one Ready / 投稿待ち article")

        base._prepare_article = gone
        with pytest.raises(base.NoteDraftError):
            revalidate_before_mutation(base, prepared)
        assert base.note_mutations == 0


def test_note_target_identity_is_required_fail_closed(monkeypatch):
    monkeypatch.delenv("NOTE_TARGET_IDENTITY", raising=False)
    with TemporaryDirectory() as tmp:
        base = _base(tmp)
        with pytest.raises(base.NoteDraftError):
            prepare_delivery(base, "a" * 32)


def _creation_base(tmp, *, mode="success"):
    base = _base(tmp)
    base.create_count = 0
    base.mode = mode

    def decode_storage_state():
        path = Path(tmp) / "storage.json"
        path.write_text("{}", encoding="utf-8")
        return path

    def create_browser_draft(title, manuscript, eyecatch_path, storage_path, *, on_stable_draft_url=None):
        del title, manuscript, eyecatch_path, storage_path
        base.create_count += 1
        url = "https://note.com/notes/opaque_draft_1/edit"
        if base.mode == "accept_before_id":
            raise base.NoteDraftError("simulated crash after accept before stable id")
        if on_stable_draft_url is not None:
            on_stable_draft_url(url)
        if base.mode == "after_id_before_verify":
            raise base.NoteDraftError("simulated failure after id record before verify")
        return url

    base._decode_storage_state = decode_storage_state
    base._create_browser_draft = create_browser_draft
    return base


def test_b11_note_creation_is_zero_when_intent_commit_fails(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        ledger.initialize()
        conn = sqlite3.connect(ledger.path)
        conn.execute(
            "CREATE TRIGGER force_intent_failure BEFORE INSERT ON deliveries "
            "BEGIN SELECT RAISE(ABORT, 'forced'); END"
        )
        conn.commit()
        conn.close()
        with pytest.raises(LedgerUnavailableError):
            create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        assert base.create_count == 0


def test_b12_draft_id_durable_write_failure_prevents_queue_update_and_second_create(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)

        class FailingDraftWriteLedger(SQLiteDeliveryLedger):
            def record_draft_created(self, *args, **kwargs):
                raise LedgerUnavailableError("forced draft-id durability failure")

        ledger = FailingDraftWriteLedger(Path(tmp) / "ledger.sqlite3")
        with pytest.raises(LedgerUnavailableError):
            create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        assert base.create_count == 1
        retry = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
        assert retry.state == DeliveryState.CREATION_UNKNOWN
        assert base.create_count == 1


def test_b04_after_id_record_before_verify_retry_reuses_same_draft(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp, mode="after_id_before_verify")
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        with pytest.raises(base.NoteDraftError):
            create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        record = ledger.get_active_by_logical_key(logical_delivery_key(prepared.snapshot))
        assert record is not None and record.state == DeliveryState.DRAFT_CREATED
        base.mode = "success"
        retry = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
        assert retry.draft_id == "opaque_draft_1"
        assert base.create_count == 1


def test_b04_after_accept_before_id_record_becomes_creation_unknown_not_second_create(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp, mode="accept_before_id")
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        with pytest.raises(base.NoteDraftError):
            create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        assert base.create_count == 1
        base.mode = "success"
        retry = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
        assert retry.state == DeliveryState.CREATION_UNKNOWN
        assert base.create_count == 1


def _queue_binding(*, posting="投稿準備中", quality="Ready", draft_id="opaque_draft_1"):
    return reconcile.QueueDraftBinding(
        page_id="queue-page-1",
        sync_id="a" * 32,
        quality=quality,
        posting=posting,
        draft_id=draft_id,
    )


def test_b01_verified_draft_exact_readback_reaches_queue_confirmed(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        monkeypatch.setattr(
            reconcile,
            "patch_and_readback_draft_binding",
            lambda *_args, **_kwargs: _queue_binding(),
        )
        record = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        assert record.state == DeliveryState.QUEUE_CONFIRMED
        assert record.last_verified_canonical_hash == prepared.snapshot.canonical_document_sha256
        assert record.queue_receipt_digest
        assert base.create_count == 1


def test_b02_queue_timeout_retry_creates_no_second_draft(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        monkeypatch.setattr(
            reconcile,
            "patch_and_readback_draft_binding",
            lambda *_args, **_kwargs: _queue_binding(),
        )
        first = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        retry = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
        assert first.state == DeliveryState.QUEUE_CONFIRMED
        assert retry.state == DeliveryState.QUEUE_CONFIRMED
        assert base.create_count == 1


def test_b03_queue_5xx_keeps_verified_draft_and_pending_state(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        monkeypatch.setattr(
            reconcile,
            "patch_and_readback_draft_binding",
            lambda *_args, **_kwargs: _queue_binding(posting="投稿待ち", draft_id=""),
        )
        record = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        retry = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
        assert record.state == DeliveryState.QUEUE_CONFIRMATION_PENDING
        assert retry.state == DeliveryState.QUEUE_CONFIRMATION_PENDING
        assert record.last_verified_canonical_hash == prepared.snapshot.canonical_document_sha256
        assert base.create_count == 1


def test_b05_queue_applied_then_result_failure_is_reconstructible_from_ledger_and_readback(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)

        class FailOnceConfirmationLedger(SQLiteDeliveryLedger):
            failed = False

            def record_queue_confirmed(self, *args, **kwargs):
                if not self.failed:
                    self.failed = True
                    raise LedgerUnavailableError("simulated result persistence failure")
                return super().record_queue_confirmed(*args, **kwargs)

        ledger = FailOnceConfirmationLedger(Path(tmp) / "ledger.sqlite3")
        monkeypatch.setattr(
            reconcile,
            "patch_and_readback_draft_binding",
            lambda *_args, **_kwargs: _queue_binding(),
        )
        with pytest.raises(LedgerUnavailableError):
            create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        durable = ledger.get_active_by_logical_key(logical_delivery_key(prepared.snapshot))
        assert durable is not None
        assert durable.state == DeliveryState.DRAFT_VERIFIED
        assert reconcile.queue_draft_binding_confirmed(
            _queue_binding(), expected_sync_id="a" * 32, draft_id="opaque_draft_1"
        )
        retry = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
        assert retry.state == DeliveryState.QUEUE_CONFIRMED
        assert base.create_count == 1


def test_b02_retry_after_queue_timeout_total_drafts_is_one(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        bindings = iter([
            _queue_binding(posting="投稿待ち", draft_id=""),
            _queue_binding(),
        ])
        monkeypatch.setattr(
            reconcile,
            "patch_and_readback_draft_binding",
            lambda *_args, **_kwargs: next(bindings),
        )
        first = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        second = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
        assert first.state == DeliveryState.QUEUE_CONFIRMATION_PENDING
        assert second.state == DeliveryState.QUEUE_CONFIRMED
        assert base.create_count == 1


def test_b03_retry_after_queue_5xx_total_drafts_is_one(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        bindings = iter([
            _queue_binding(posting="投稿待ち", draft_id=""),
            _queue_binding(),
        ])
        monkeypatch.setattr(reconcile, "patch_and_readback_draft_binding", lambda *_a, **_k: next(bindings))
        create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        retry = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
        assert retry.state == DeliveryState.QUEUE_CONFIRMED
        assert base.create_count == 1


def test_b04_retry_at_each_crash_boundary_never_creates_second_draft(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    for mode, expected_state in (
        ("after_id_before_verify", DeliveryState.DRAFT_CREATED),
        ("accept_before_id", DeliveryState.CREATION_UNKNOWN),
    ):
        with TemporaryDirectory() as tmp:
            base = _creation_base(tmp, mode=mode)
            prepared = prepare_delivery(base, "a" * 32)
            ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
            with pytest.raises(base.NoteDraftError):
                create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
            base.mode = "success"
            retry = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-b")
            assert retry.state == expected_state
            assert base.create_count == 1


def test_b05_reporting_failure_reconstructs_result_without_create(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)

        class FailOnceConfirmationLedger(SQLiteDeliveryLedger):
            failed = False

            def record_queue_confirmed(self, *args, **kwargs):
                if not self.failed:
                    self.failed = True
                    raise LedgerUnavailableError("simulated result persistence failure")
                return super().record_queue_confirmed(*args, **kwargs)

        ledger = FailOnceConfirmationLedger(Path(tmp) / "ledger.sqlite3")
        monkeypatch.setattr(reconcile, "patch_and_readback_draft_binding", lambda *_a, **_k: _queue_binding())
        with pytest.raises(LedgerUnavailableError):
            create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        result = delivery_runtime.reconcile_exact_delivery(
            base,
            ledger,
            sync_id="a" * 32,
            note_target="trendhub-biz",
        )
        assert result["status"] == "queue_confirmed"
        assert result["draft_id"] == "opaque_draft_1"
        assert base.create_count == 1


def test_b06_same_operation_key_retry_total_drafts_is_one(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        monkeypatch.setattr(reconcile, "patch_and_readback_draft_binding", lambda *_a, **_k: _queue_binding())
        first = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        second = create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a-retry")
        assert first.operation_key == second.operation_key
        assert second.state == DeliveryState.QUEUE_CONFIRMED
        assert base.create_count == 1


def test_b07_process_restart_with_reopened_sqlite_total_drafts_is_one(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        path = Path(tmp) / "ledger.sqlite3"
        first_ledger = SQLiteDeliveryLedger(path)
        monkeypatch.setattr(
            reconcile,
            "patch_and_readback_draft_binding",
            lambda *_a, **_k: _queue_binding(posting="投稿待ち", draft_id=""),
        )
        first = create_or_resume_delivery(base, first_ledger, prepared, run_correlation_id="run-a")
        assert first.state == DeliveryState.QUEUE_CONFIRMATION_PENDING

        reopened = SQLiteDeliveryLedger(path)
        monkeypatch.setattr(reconcile, "patch_and_readback_draft_binding", lambda *_a, **_k: _queue_binding())
        retry = create_or_resume_delivery(base, reopened, prepared, run_correlation_id="run-b")
        assert retry.state == DeliveryState.QUEUE_CONFIRMED
        assert base.create_count == 1


def test_b08_second_worker_same_logical_delivery_cannot_create(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        path = Path(tmp) / "ledger.sqlite3"
        first_ledger = SQLiteDeliveryLedger(path)
        monkeypatch.setattr(
            reconcile,
            "patch_and_readback_draft_binding",
            lambda *_a, **_k: _queue_binding(posting="投稿待ち", draft_id=""),
        )
        create_or_resume_delivery(base, first_ledger, prepared, run_correlation_id="worker-a")
        second_worker = SQLiteDeliveryLedger(path)
        monkeypatch.setattr(reconcile, "patch_and_readback_draft_binding", lambda *_a, **_k: _queue_binding())
        result = create_or_resume_delivery(base, second_worker, prepared, run_correlation_id="worker-b")
        assert result.state == DeliveryState.QUEUE_CONFIRMED
        assert base.create_count == 1


def test_b09_same_revision_different_run_reconciles_existing_record(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        monkeypatch.setattr(
            reconcile,
            "patch_and_readback_draft_binding",
            lambda *_a, **_k: _queue_binding(posting="投稿待ち", draft_id=""),
        )
        create_or_resume_delivery(base, ledger, prepared, run_correlation_id="run-a")
        monkeypatch.setattr(reconcile, "patch_and_readback_draft_binding", lambda *_a, **_k: _queue_binding())
        result = delivery_runtime.reconcile_exact_delivery(
            base,
            ledger,
            sync_id="a" * 32,
            note_target="trendhub-biz",
        )
        assert result["status"] == "queue_confirmed"
        assert result["record"].state == DeliveryState.QUEUE_CONFIRMED
        assert base.create_count == 1


def test_b17_new_revision_with_unresolved_old_intent_cannot_create(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        old_prepared = prepare_delivery(base, "a" * 32)
        ledger = SQLiteDeliveryLedger(Path(tmp) / "ledger.sqlite3")
        old_intent = ledger.begin_or_load(old_prepared.snapshot, run_correlation_id="run-a")
        assert old_intent.creation_authorized

        base.article["manuscript_sha256"] = "9" * 64
        changed = prepare_delivery(base, "a" * 32)
        result = create_or_resume_delivery(base, ledger, changed, run_correlation_id="run-b")
        assert result.operation_key == old_intent.record.operation_key
        assert result.state == DeliveryState.CREATE_INTENT_RECORDED
        assert base.create_count == 0


def test_b18_unavailable_ledger_overrides_eligible_queue_and_creates_zero(monkeypatch):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    with TemporaryDirectory() as tmp:
        base = _creation_base(tmp)
        prepared = prepare_delivery(base, "a" * 32)
        impossible = SQLiteDeliveryLedger(Path("/dev/null") / "delivery.sqlite3")
        with pytest.raises(LedgerUnavailableError):
            create_or_resume_delivery(base, impossible, prepared, run_correlation_id="run-a")
        assert base.create_count == 0


# TASK3_RECONCILED_RETRY_RUNTIME_TESTS
_RUNTIME_STRONG_ZERO_EVIDENCE = (
    "creation_absence_confirmed_strong_zero:" + "c" * 64
)


def _prepared_for_runtime_retry(monkeypatch, tmp_path, *, mode="success"):
    monkeypatch.setenv("NOTE_TARGET_IDENTITY", "trendhub-biz")
    base = _creation_base(tmp_path, mode=mode)
    return base, prepare_delivery(base, "a" * 32)


def _prepare_runtime_manual_reconciliation(ledger, prepared):
    first = ledger.begin_or_load(prepared.snapshot, run_correlation_id="run-original")
    unknown = ledger.record_blocked(
        first.record.operation_key,
        state=DeliveryState.CREATION_UNKNOWN,
        category="creation_result_ambiguous",
        expected_version=first.record.state_version,
    )
    return ledger.record_blocked(
        unknown.operation_key,
        state=DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        category=_RUNTIME_STRONG_ZERO_EVIDENCE,
        expected_version=unknown.state_version,
    )


def test_reconciled_retry_uses_dedicated_authority_and_creates_exactly_once(tmp_path, monkeypatch):
    ledger = SQLiteDeliveryLedger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    base, prepared = _prepared_for_runtime_retry(monkeypatch, tmp_path)
    manual = _prepare_runtime_manual_reconciliation(ledger, prepared)
    monkeypatch.setattr(
        delivery_runtime.reconcile,
        "patch_and_readback_draft_binding",
        lambda *args, **kwargs: _queue_binding(),
    )

    final = delivery_runtime.create_reconciled_retry(
        base,
        ledger,
        prepared,
        run_correlation_id="run-retry",
        expected_version=manual.state_version,
    )
    assert final.state == DeliveryState.QUEUE_CONFIRMED
    assert final.draft_id == "opaque_draft_1"
    assert base.create_count == 1

    ordinary = delivery_runtime.create_or_resume_delivery(
        base,
        ledger,
        prepared,
        run_correlation_id="run-ordinary",
    )
    assert ordinary.state == DeliveryState.QUEUE_CONFIRMED
    assert base.create_count == 1


def test_reconciled_retry_rejected_authority_performs_zero_browser_mutation(tmp_path, monkeypatch):
    ledger = SQLiteDeliveryLedger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    base, prepared = _prepared_for_runtime_retry(monkeypatch, tmp_path)
    first = ledger.begin_or_load(prepared.snapshot, run_correlation_id="run-original")

    returned = delivery_runtime.create_reconciled_retry(
        base,
        ledger,
        prepared,
        run_correlation_id="run-retry",
        expected_version=first.record.state_version,
    )
    assert returned.state == DeliveryState.CREATE_INTENT_RECORDED
    assert base.create_count == 0


def test_reconciled_retry_stale_version_performs_zero_browser_mutation(tmp_path, monkeypatch):
    ledger = SQLiteDeliveryLedger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    base, prepared = _prepared_for_runtime_retry(monkeypatch, tmp_path)
    manual = _prepare_runtime_manual_reconciliation(ledger, prepared)

    with pytest.raises(ConcurrentStateChange, match="state_version_mismatch"):
        delivery_runtime.create_reconciled_retry(
            base,
            ledger,
            prepared,
            run_correlation_id="run-retry",
            expected_version=manual.state_version - 1,
        )
    assert base.create_count == 0


def test_reconciled_retry_browser_ambiguity_returns_to_creation_unknown(tmp_path, monkeypatch):
    ledger = SQLiteDeliveryLedger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    base, prepared = _prepared_for_runtime_retry(monkeypatch, tmp_path, mode="accept_before_id")
    manual = _prepare_runtime_manual_reconciliation(ledger, prepared)

    with pytest.raises(base.NoteDraftError):
        delivery_runtime.create_reconciled_retry(
            base,
            ledger,
            prepared,
            run_correlation_id="run-retry",
            expected_version=manual.state_version,
        )
    blocked = ledger.get_by_operation_key(manual.operation_key)
    assert blocked is not None
    assert blocked.state == DeliveryState.CREATION_UNKNOWN
    assert base.create_count == 1

    base.mode = "success"
    resumed = delivery_runtime.create_or_resume_delivery(
        base,
        ledger,
        prepared,
        run_correlation_id="run-ordinary",
    )
    assert resumed.state == DeliveryState.CREATION_UNKNOWN
    assert base.create_count == 1


def test_reconciled_retry_after_stable_id_failure_never_recreates(tmp_path, monkeypatch):
    ledger = SQLiteDeliveryLedger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    base, prepared = _prepared_for_runtime_retry(monkeypatch, tmp_path, mode="after_id_before_verify")
    manual = _prepare_runtime_manual_reconciliation(ledger, prepared)

    with pytest.raises(base.NoteDraftError):
        delivery_runtime.create_reconciled_retry(
            base,
            ledger,
            prepared,
            run_correlation_id="run-retry",
            expected_version=manual.state_version,
        )
    created = ledger.get_by_operation_key(manual.operation_key)
    assert created is not None
    assert created.state == DeliveryState.DRAFT_CREATED
    assert created.draft_id == "opaque_draft_1"
    assert base.create_count == 1

    base.mode = "success"
    returned = delivery_runtime.create_reconciled_retry(
        base,
        ledger,
        prepared,
        run_correlation_id="run-retry-2",
        expected_version=created.state_version,
    )
    assert returned.state == DeliveryState.DRAFT_CREATED
    assert returned.draft_id == "opaque_draft_1"
    assert base.create_count == 1


def test_reconciled_retry_queue_readback_mismatch_never_recreates(tmp_path, monkeypatch):
    ledger = SQLiteDeliveryLedger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    base, prepared = _prepared_for_runtime_retry(monkeypatch, tmp_path)
    manual = _prepare_runtime_manual_reconciliation(ledger, prepared)
    monkeypatch.setattr(
        delivery_runtime.reconcile,
        "patch_and_readback_draft_binding",
        lambda *args, **kwargs: _queue_binding(posting="投稿待ち", draft_id=""),
    )

    pending = delivery_runtime.create_reconciled_retry(
        base,
        ledger,
        prepared,
        run_correlation_id="run-retry",
        expected_version=manual.state_version,
    )
    assert pending.state == DeliveryState.QUEUE_CONFIRMATION_PENDING
    assert pending.draft_id == "opaque_draft_1"
    assert base.create_count == 1

    ordinary = delivery_runtime.create_or_resume_delivery(
        base,
        ledger,
        prepared,
        run_correlation_id="run-ordinary",
    )
    assert ordinary.state == DeliveryState.QUEUE_CONFIRMATION_PENDING
    assert base.create_count == 1
