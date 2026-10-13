from datetime import datetime, timezone

from v2_shadow_selection import normalize_candidate, rank_candidates, screen_candidate


NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


def _candidate(url: str, published_at):
    return normalize_candidate(
        {
            "url": url,
            "title": "Equal quality candidate",
            "description": (
                "Same substantive description used to isolate deterministic freshness "
                "scoring from all other candidate quality signals."
            ),
            "published_at": published_at,
        },
        provider="feed",
        acquired_at=NOW,
    )


def test_fresh_candidate_ranks_above_stale_candidate_when_other_signals_match():
    stale = _candidate("https://example.com/a-stale", "2026-08-01T00:00:00+00:00")
    fresh = _candidate("https://example.com/z-fresh", "2026-10-13T00:00:00+00:00")

    ranked = rank_candidates([stale, fresh], now=NOW)

    assert ranked[0]["candidate_identity"] == "https://example.com/z-fresh"
    assert ranked[0]["screening_score"] > ranked[1]["screening_score"]
    assert "fresh_within_7d" in ranked[0]["screening_reasons"]
    assert "stale_over_30d" in ranked[1]["screening_reasons"]


def test_unparseable_timestamp_receives_no_freshness_bonus():
    invalid = _candidate("https://example.com/invalid", "not-a-date")
    missing = _candidate("https://example.com/missing", None)

    invalid_screened = screen_candidate(invalid, now=NOW)
    missing_screened = screen_candidate(missing, now=NOW)

    assert invalid_screened["screening_score"] == missing_screened["screening_score"]
    assert "source_timestamp_invalid" in invalid_screened["screening_reasons"]


def test_materially_future_timestamp_receives_no_freshness_bonus():
    future = _candidate("https://example.com/future", "2026-10-20T00:00:00+00:00")
    missing = _candidate("https://example.com/missing", None)

    future_screened = screen_candidate(future, now=NOW)
    missing_screened = screen_candidate(missing, now=NOW)

    assert future_screened["screening_score"] == missing_screened["screening_score"]
    assert "source_timestamp_future" in future_screened["screening_reasons"]
