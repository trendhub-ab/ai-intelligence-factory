"""Provider-free CAS proof for canonical Gemini runtime-state ledger."""
from __future__ import annotations
import base64
import json

import pipeline as p


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
