import os

import pytest

import note_delivery_runtime as runtime
from note_delivery_gcs import GCSDeliveryLedger
from note_delivery_ledger import LedgerUnavailableError, SQLiteDeliveryLedger


class DummyGCSLedger:
    def __init__(self, bucket_name: str, *, prefix: str = "delivery/v1", client=None):
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.client = client


def test_production_factory_requires_explicit_backend(monkeypatch):
    monkeypatch.delenv("NOTE_DELIVERY_LEDGER_BACKEND", raising=False)
    monkeypatch.delenv("NOTE_DELIVERY_LEDGER_BUCKET", raising=False)
    monkeypatch.delenv("NOTE_DELIVERY_LEDGER_PATH", raising=False)
    with pytest.raises(LedgerUnavailableError, match="ledger_backend_required"):
        runtime.delivery_ledger_from_environment()


def test_gcs_backend_requires_bucket(monkeypatch):
    monkeypatch.setenv("NOTE_DELIVERY_LEDGER_BACKEND", "gcs")
    monkeypatch.delenv("NOTE_DELIVERY_LEDGER_BUCKET", raising=False)
    with pytest.raises(LedgerUnavailableError, match="gcs_bucket_required"):
        runtime.delivery_ledger_from_environment()


def test_gcs_backend_constructs_cloud_ledger(monkeypatch):
    monkeypatch.setenv("NOTE_DELIVERY_LEDGER_BACKEND", "gcs")
    monkeypatch.setenv("NOTE_DELIVERY_LEDGER_BUCKET", "private-ledger")
    monkeypatch.setenv("NOTE_DELIVERY_LEDGER_PREFIX", "delivery/v1")
    monkeypatch.setattr(runtime, "GCSDeliveryLedger", DummyGCSLedger)
    ledger = runtime.delivery_ledger_from_environment()
    assert isinstance(ledger, DummyGCSLedger)
    assert ledger.bucket_name == "private-ledger"
    assert ledger.prefix == "delivery/v1"


def test_unknown_backend_fails_closed(monkeypatch):
    monkeypatch.setenv("NOTE_DELIVERY_LEDGER_BACKEND", "mystery")
    with pytest.raises(LedgerUnavailableError, match="unsupported_ledger_backend"):
        runtime.delivery_ledger_from_environment()


def test_sqlite_is_reference_only_and_must_be_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTE_DELIVERY_LEDGER_BACKEND", "sqlite")
    monkeypatch.setenv("NOTE_DELIVERY_LEDGER_PATH", str(tmp_path / "reference.sqlite3"))
    ledger = runtime.delivery_ledger_from_environment()
    assert isinstance(ledger, SQLiteDeliveryLedger)
    assert ledger.path == tmp_path / "reference.sqlite3"


def test_sqlite_without_explicit_path_fails_closed(monkeypatch):
    monkeypatch.setenv("NOTE_DELIVERY_LEDGER_BACKEND", "sqlite")
    monkeypatch.delenv("NOTE_DELIVERY_LEDGER_PATH", raising=False)
    with pytest.raises(LedgerUnavailableError, match="sqlite_ledger_path_required"):
        runtime.delivery_ledger_from_environment()
