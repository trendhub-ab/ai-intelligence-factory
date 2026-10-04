import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import note_publication_reconcile as reconcile
from note_delivery_ledger import (
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
        assert retry.state == DeliveryState.DRAFT_VERIFIED
        assert base.create_count == 1
