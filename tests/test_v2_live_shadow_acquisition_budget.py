from __future__ import annotations

from datetime import datetime, timezone

import pytest

from v2_live_shadow_acquisition import LiveAcquisitionConfig, run_bounded_live_shadow


NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, *, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def http_get(url, **kwargs):
    if url.endswith("topstories.json"):
        return FakeResponse(json_data=[101])
    if "/101.json" in url:
        return FakeResponse(
            json_data={
                "id": 101,
                "type": "story",
                "title": "Current AI release",
                "url": "https://vendor.example/releases/current",
                "time": 1791930000,
                "score": 150,
                "descendants": 50,
            }
        )
    if "export.arxiv.org" in url:
        return FakeResponse(text='<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>')
    raise AssertionError(url)


def _run(*, budget_marker="omitted"):
    calls = []

    def deep_dive(candidate):
        calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": True}

    kwargs = {
        "http_get": http_get,
        "deep_dive": deep_dive,
        "config": LiveAcquisitionConfig(hn_limit=1, arxiv_limit=1, total_candidate_limit=2),
        "now": NOW,
        "run_id": f"budget-{budget_marker}",
    }
    if budget_marker != "omitted":
        kwargs["max_deep_dive_attempts"] = budget_marker
    report = run_bounded_live_shadow(**kwargs)
    return report, calls


def test_default_budget_preserves_v2_002_one_attempt_behavior():
    report, calls = _run()

    assert report["deep_dive_attempted_count"] == 1
    assert report["actual_calls"]["deep_dive"] == 1
    assert len(calls) == 1


def test_explicit_zero_budget_never_invokes_deep_dive():
    report, calls = _run(budget_marker=0)

    assert calls == []
    assert report["deep_dive_attempted_count"] == 0
    assert report["actual_calls"]["deep_dive"] == 0
    assert report["v2_selected_candidate_identity"] is None


@pytest.mark.parametrize("value", [-4, "invalid", None])
def test_non_positive_or_invalid_budget_fails_closed_to_zero(value):
    report, calls = _run(budget_marker=value)

    assert calls == []
    assert report["deep_dive_attempted_count"] == 0
    assert report["actual_calls"]["deep_dive"] == 0


@pytest.mark.parametrize("value", [1, 2, 99])
def test_positive_budget_is_clamped_to_one(value):
    report, calls = _run(budget_marker=value)

    assert report["deep_dive_attempted_count"] == 1
    assert report["actual_calls"]["deep_dive"] == 1
    assert len(calls) == 1
