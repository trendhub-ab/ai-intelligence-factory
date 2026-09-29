import types
import stale_ready_batch_revalidation as batch


def test_batch_is_conservatively_bounded():
    assert batch.DEFAULT_BATCH_SIZE==2
    assert batch.MAX_BATCH_SIZE==3


def test_repo_uses_persisted_primary_url():
    state={"title":"x","source":"ArXiv","original_url":"https://example.com/discovery","primary_url":"https://example.com/primary"}
    repo=batch._repo({"properties":{}},state)
    assert repo["primaryUrl"]=="https://example.com/primary"
    assert repo["sourceDetails"]["external_url"]=="https://example.com/primary"


def test_source_contract_has_toctou_and_no_force_ready():
    from pathlib import Path
    source=Path("stale_ready_batch_revalidation.py").read_text(encoding="utf-8")
    assert "_fetch_page(page_id)" in source
    assert "_source_has_current_ready_manuscript" in source
    assert "_delivery_recovery_state" in source
    assert "persist_results=True" in source
    assert "ARTICLE_STATUS_READY" not in source
    assert "budget +=" not in source


def test_delivery_recovery_state_blocks_prepared_and_posted(monkeypatch):
    monkeypatch.setattr(batch.nrs, "DEST_DATA_SOURCE_ID", "dest")
    monkeypatch.setattr(batch.nrs, "classify_exact_delivery_state", lambda _sid: "already_delivered")
    assert batch._delivery_recovery_state("a" * 32) == "already_delivered"


def test_delivery_recovery_state_fails_closed_on_lookup_error(monkeypatch):
    monkeypatch.setattr(batch.nrs, "DEST_DATA_SOURCE_ID", "dest")
    def broken(_sid):
        raise RuntimeError("notion down")
    monkeypatch.setattr(batch.nrs, "classify_exact_delivery_state", broken)
    assert batch._delivery_recovery_state("a" * 32) == "unavailable"
