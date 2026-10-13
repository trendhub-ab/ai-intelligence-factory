import sys
from types import SimpleNamespace

import article_revalidation


class _Logger:
    def __init__(self):
        self.rows = []

    def info(self, *args, **kwargs):
        self.rows.append(("info", args))

    def warning(self, *args, **kwargs):
        self.rows.append(("warning", args))


def _pipeline():
    return SimpleNamespace(logger=_Logger())


def test_missing_delivery_authority_blocks_existing_article_recovery(monkeypatch):
    fake_ready_sync = SimpleNamespace(
        DEST_DATA_SOURCE_ID="",
        DEST_DATABASE_ID="",
        classify_exact_delivery_state=lambda _: "not_queued",
    )
    monkeypatch.setitem(sys.modules, "note_ready_sync", fake_ready_sync)

    assert article_revalidation._automatic_existing_recovery_allowed(
        _pipeline(), "a" * 32
    ) is False


def test_already_delivered_blocks_existing_article_recovery(monkeypatch):
    fake_ready_sync = SimpleNamespace(
        DEST_DATA_SOURCE_ID="configured",
        DEST_DATABASE_ID="",
        classify_exact_delivery_state=lambda _: "already_delivered",
    )
    monkeypatch.setitem(sys.modules, "note_ready_sync", fake_ready_sync)

    assert article_revalidation._automatic_existing_recovery_allowed(
        _pipeline(), "b" * 32
    ) is False


def test_verified_prepublication_state_remains_recoverable(monkeypatch):
    fake_ready_sync = SimpleNamespace(
        DEST_DATA_SOURCE_ID="configured",
        DEST_DATABASE_ID="",
        classify_exact_delivery_state=lambda _: "not_queued",
    )
    monkeypatch.setitem(sys.modules, "note_ready_sync", fake_ready_sync)

    assert article_revalidation._automatic_existing_recovery_allowed(
        _pipeline(), "c" * 32
    ) is True
