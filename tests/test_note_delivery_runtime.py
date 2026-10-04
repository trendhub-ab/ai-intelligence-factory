from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from note_delivery_runtime import prepare_delivery, revalidate_before_mutation


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
