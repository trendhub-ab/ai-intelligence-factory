from datetime import datetime, timedelta, timezone

import run260_gemini_model_routing as routing


def _row(ts, model, outcome):
    return {
        "timestamp": ts.isoformat(),
        "model": model,
        "kind": "deep_dive",
        "outcome": outcome,
        "error_type": "ServiceUnavailable" if outcome == "error" else "",
    }


def test_recent_503_outweighs_stale_successes(monkeypatch):
    monkeypatch.setenv("GEMINI_PROVIDER_HEALTH_RECENCY_HALF_LIFE_HOURS", "3")
    now = datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc)
    history = [
        _row(now - timedelta(hours=12), "gemini-3.6-flash", "success"),
        _row(now - timedelta(hours=10), "gemini-3.6-flash", "success"),
        _row(now - timedelta(minutes=5), "gemini-3.6-flash", "error"),
        _row(now - timedelta(hours=2), "gemini-3.8-flash", "success"),
        _row(now - timedelta(hours=1), "gemini-3.8-flash", "error"),
    ]
    ranked = routing._health_ranked_pool(
        ["gemini-3.6-flash", "gemini-3.8-flash"], history, now=now
    )
    assert ranked == ["gemini-3.8-flash", "gemini-3.6-flash"]


def test_recent_success_still_wins(monkeypatch):
    monkeypatch.setenv("GEMINI_PROVIDER_HEALTH_RECENCY_HALF_LIFE_HOURS", "3")
    now = datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc)
    history = [
        _row(now - timedelta(minutes=5), "gemini-3.7-flash", "success"),
        _row(now - timedelta(minutes=5), "gemini-3.8-flash", "error"),
    ]
    ranked = routing._health_ranked_pool(
        ["gemini-3.8-flash", "gemini-3.7-flash"], history, now=now
    )
    assert ranked == ["gemini-3.7-flash", "gemini-3.8-flash"]
