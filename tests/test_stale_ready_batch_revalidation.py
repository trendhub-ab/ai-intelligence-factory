import types
import pytest
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
    assert "_is_posted" in source
    assert "persist_results=True" in source
    assert "ARTICLE_STATUS_READY" not in source
    assert "budget +=" not in source


def _pipeline(calls):
    class Budget:
        budget=12
        used=0

    class Logger:
        def info(self, *args, **kwargs):
            return None

    def generate(repo, **kwargs):
        calls.append({"repo":repo,"kwargs":kwargs})
        return "accepted article"

    return types.SimpleNamespace(
        DEEP_DIVE_MODEL_BUDGET=Budget(),
        initialize_runtime=lambda: None,
        legal_safety_gate=lambda repo:(True,"SAFE"),
        generate_intelligence_report=generate,
        logger=Logger(),
    )


def _state(title, sync_id):
    return {
        "title":title,
        "sync_id":sync_id,
        "source":"HackerNews",
        "original_url":"https://example.com/discovery",
        "primary_url":"https://example.com/primary",
    }


def test_exact_target_persists_only_matching_stale_ready(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARTICLE_REVALIDATION_EXACT_TARGET","target article")
    pages=[{"id":"a"},{"id":"b"}]
    states={"a":_state("other article","sync-a"),"b":_state("target article","sync-b")}
    monkeypatch.setattr(batch.nrs,"_query_db",lambda *args,**kwargs:pages)
    monkeypatch.setattr(batch.nrs,"_source_state",lambda page:states[page["id"]])
    monkeypatch.setattr(batch,"_fetch_page",lambda page_id:{"id":page_id})
    monkeypatch.setattr(batch.nrs,"_source_has_current_ready_manuscript",lambda sync_id:False)
    monkeypatch.setattr(batch,"_is_posted",lambda sync_id:False)
    calls=[]
    result=batch.run(_pipeline(calls))
    assert result["exact_target"]=="target article"
    assert result["batch_limit"]==1
    assert result["attempted"]==1
    assert result["passed"]==1
    assert len(calls)==1
    assert calls[0]["repo"]["nameWithOwner"]=="target article"
    assert calls[0]["kwargs"]["notion_page_id"]=="b"
    assert calls[0]["kwargs"]["persist_results"] is True


def test_exact_target_missing_fails_before_provider(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARTICLE_REVALIDATION_EXACT_TARGET","missing article")
    pages=[{"id":"a"}]
    states={"a":_state("other article","sync-a")}
    monkeypatch.setattr(batch.nrs,"_query_db",lambda *args,**kwargs:pages)
    monkeypatch.setattr(batch.nrs,"_source_state",lambda page:states[page["id"]])
    calls=[]
    with pytest.raises(RuntimeError,match="exact target count mismatch"):
        batch.run(_pipeline(calls))
    assert calls==[]


def test_exact_target_title_change_fails_toctou_before_provider(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARTICLE_REVALIDATION_EXACT_TARGET","target article")
    pages=[{"id":"a","snapshot":True}]
    initial=_state("target article","sync-a")
    changed=_state("changed article","sync-a")
    monkeypatch.setattr(batch.nrs,"_query_db",lambda *args,**kwargs:pages)
    monkeypatch.setattr(batch.nrs,"_source_state",lambda page:initial if page.get("snapshot") else changed)
    monkeypatch.setattr(batch,"_fetch_page",lambda page_id:{"id":page_id})
    calls=[]
    with pytest.raises(RuntimeError,match="changed during TOCTOU"):
        batch.run(_pipeline(calls))
    assert calls==[]
