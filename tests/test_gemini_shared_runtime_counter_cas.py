"""Provider-free CAS proof for canonical Gemini runtime-state ledger."""
from __future__ import annotations
import base64
import json

import pipeline as p
from run203_runtime_state_channel import install_canonical_flash_alias_budget


class Response:
    def __init__(self, code, value=None, text=""):
        self.status_code = code
        self._value = value or {}
        self.text = text

    def json(self):
        return self._value


def test_runtime_ledger_reservation_uses_single_branch_and_cas(monkeypatch):
    state = {"schema_version": 3, "quota_date": "2026-10-24", "counter_scopes": {}}
    writes = []
    reads = []
    monkeypatch.setattr(p, "GH_PAT", "test-fixture-token")
    counter = p.PersistentGeminiDailyCounter(
        True, {"gemini-3.8-flash": 5}, 5,
        ".runtime/gemini_daily_usage.json", "America/Los_Angeles",
        quota_scope_id="trendhub-ab/ai-intelligence-factory",
    )
    counter.repo = "trendhub-ab/ai-intelligence-factory"
    counter.branch = "runtime-state"
    monkeypatch.setattr(counter, "_quota_date", lambda: "2026-10-24")

    def get(url, headers, params, timeout):
        reads.append(params["ref"])
        assert url.endswith("/contents/.runtime/gemini_daily_usage.json")
        content = base64.b64encode(json.dumps(state).encode()).decode()
        return Response(200, {"content": content, "sha": "fixture-blob-sha"})

    def put(url, headers, json, timeout):
        writes.append(json)
        assert url.endswith("/contents/.runtime/gemini_daily_usage.json")
        return Response(200)

    monkeypatch.setattr(p.requests, "get", get)
    monkeypatch.setattr(p.requests, "put", put)
    counter.reserve("deep_dive", model_name="gemini-3.8-flash")
    assert reads == ["runtime-state"]
    assert len(writes) == 1
    assert writes[0]["branch"] == "runtime-state"
    assert writes[0]["sha"] == "fixture-blob-sha"
    decoded = json.loads(base64.b64decode(writes[0]["content"]))
    entry = decoded["counter_scopes"][counter.counter_scope]["models"]["gemini-3.8-flash"]
    assert entry["used"] == 1
    assert entry["by_kind"] == {"deep_dive": 1}
    assert counter.session_used == 1


def test_branch_cas_conflict_never_skips_count(monkeypatch):
    state = {"schema_version": 3, "quota_date": "2026-10-24", "counter_scopes": {}}
    attempts = []
    monkeypatch.setattr(p, "GH_PAT", "test-fixture-token")
    monkeypatch.setattr(p.time, "sleep", lambda _: None)
    counter = p.PersistentGeminiDailyCounter(
        True, {"gemini-3.8-flash": 5}, 5,
        ".runtime/gemini_daily_usage.json", "America/Los_Angeles",
        quota_scope_id="trendhub-ab/ai-intelligence-factory",
    )
    counter.repo = "trendhub-ab/ai-intelligence-factory"
    counter.branch = "runtime-state"
    monkeypatch.setattr(counter, "_quota_date", lambda: "2026-10-24")

    def get(url, headers, params, timeout):
        assert params["ref"] == "runtime-state"
        payload = base64.b64encode(json.dumps(state).encode()).decode()
        return Response(200, {"content": payload, "sha": "old-blob"})

    def put(url, headers, json, timeout):
        attempts.append(json)
        if len(attempts) == 1:
            # Simulate another run winning the GitHub CAS race.
            state["counter_scopes"] = {
                counter.counter_scope: {
                    "models": {
                        "gemini-3.8-flash": {
                            "used": 2, "by_kind": {"deep_dive": 2},
                            "exhausted": False,
                        }
                    }
                }
            }
            return Response(409, text='{"message":"sha conflict"}')
        return Response(200)

    monkeypatch.setattr(p.requests, "get", get)
    monkeypatch.setattr(p.requests, "put", put)
    counter.reserve("deep_dive", model_name="gemini-3.8-flash")
    assert len(attempts) == 2
    saved = json.loads(base64.b64decode(attempts[1]["content"]))
    used = saved["counter_scopes"][counter.counter_scope]["models"]["gemini-3.8-flash"]
    assert used["used"] == 3
    assert used["by_kind"]["deep_dive"] == 3

def test_canonical_36_cap_blocks_combined_35_and_36_usage(monkeypatch):
    """These two historical names route to one physical Gemini 3.6 model."""
    import copy
    import pytest
    monkeypatch.setattr(p, "GH_PAT", "test-fixture-token")
    counter = p.PersistentGeminiDailyCounter(
        True, {"gemini-3.5-flash":18,"gemini-3.6-flash":18},18,
        ".runtime/gemini_daily_usage.json", "America/Los_Angeles",
        quota_scope_id="trendhub-ab/ai-intelligence-factory"
    )
    counter.repo="trendhub-ab/ai-intelligence-factory"
    counter.branch="runtime-state"
    install_canonical_flash_alias_budget(counter,p.GeminiBudgetExceededError)
    monkeypatch.setattr(counter,"_quota_date",lambda:"2026-10-26")
    state={"schema_version":3,"quota_date":"2026-10-26",
           "counter_scopes":{counter.counter_scope:{"models":{
               "gemini-3.5-flash":{"used":12,"by_kind":{},"exhausted":False},
               "gemini-3.6-flash":{"used":6,"by_kind":{},"exhausted":False}
           }}}}
    writes=[]
    monkeypatch.setattr(counter,"_read_remote",lambda:(copy.deepcopy(state),"sha"))
    monkeypatch.setattr(counter,"_write_remote",lambda *a,**kw:writes.append(a))
    with pytest.raises(p.GeminiBudgetExceededError,match="budget exhausted"):
        counter.reserve("deep_dive",model_name="gemini-3.6-flash")
    assert not writes
    with pytest.raises(p.GeminiBudgetExceededError,match="budget exhausted"):
        counter.reserve("deep_dive",model_name="gemini-3.5-flash")
    assert not writes


def test_canonical_38_cap_allows_final_slot_and_preserves_other_models(monkeypatch):
    import copy
    monkeypatch.setattr(p, "GH_PAT", "test-fixture-token")
    counter=p.PersistentGeminiDailyCounter(
        True,{"gemini-3.7-flash":18,"gemini-3.8-flash":18},18,
        ".runtime/gemini_daily_usage.json","America/Los_Angeles",
        quota_scope_id="trendhub-ab/ai-intelligence-factory"
    )
    counter.repo="trendhub-ab/ai-intelligence-factory"
    counter.branch="runtime-state"
    install_canonical_flash_alias_budget(counter,p.GeminiBudgetExceededError)
    monkeypatch.setattr(counter,"_quota_date",lambda:"2026-10-26")
    state={"schema_version":3,"quota_date":"2026-10-26",
           "counter_scopes":{counter.counter_scope:{"models":{
               "gemini-3.7-flash":{"used":12,"by_kind":{"legacy":12},"exhausted":False},
               "gemini-3.8-flash":{"used":5,"by_kind":{"quality_retry":5},"exhausted":False},
               "gemini-3.5-flash-lite":{"used":20,"by_kind":{},"exhausted":False}
           }}}}
    writes=[]
    monkeypatch.setattr(counter,"_read_remote",lambda:(copy.deepcopy(state),"sha"))
    monkeypatch.setattr(counter,"_write_remote",lambda data,sha:writes.append(copy.deepcopy(data)))
    counter.reserve("deep_dive",model_name="gemini-3.8-flash")
    models=writes[0]["counter_scopes"][counter.counter_scope]["models"]
    assert models["gemini-3.8-flash"]["used"]==6
    assert models["gemini-3.7-flash"]["used"]==12
    assert models["gemini-3.5-flash-lite"]["used"]==20
