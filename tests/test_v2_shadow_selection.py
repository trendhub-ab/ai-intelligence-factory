from datetime import datetime, timezone

import pytest

from v2_shadow_selection import (
    ShadowConfig,
    deduplicate_candidates,
    normalize_candidate,
    rank_candidates,
    screen_candidate,
)


NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


def test_normalize_candidate_builds_stable_identity_and_contract():
    raw = {
        "primary_url": "https://example.com/item?utm_source=test",
        "title": "Example launch",
        "description": "A concrete product update with enough detail to evaluate.",
        "published_at": "2026-10-13T12:00:00+00:00",
    }

    result = normalize_candidate(raw, provider="official", acquired_at=NOW)

    assert result["candidate_identity"] == "https://example.com/item"
    assert result["provider"] == "official"
    assert result["primary_url"] == "https://example.com/item?utm_source=test"
    assert result["title"] == "Example launch"
    assert result["description"].startswith("A concrete product update")
    assert result["source_timestamp"] == "2026-10-13T12:00:00+00:00"
    assert result["acquired_at"] == NOW.isoformat()


def test_normalize_candidate_rejects_missing_identity_inputs():
    with pytest.raises(ValueError, match="candidate"):
        normalize_candidate(
            {"description": "No title and no URL"},
            provider="broken",
            acquired_at=NOW,
        )


def test_deduplicate_candidates_collapses_tracking_variants_deterministically():
    first = normalize_candidate(
        {
            "url": "https://example.com/item?utm_campaign=a",
            "title": "First",
            "description": "First description with concrete evidence.",
        },
        provider="one",
        acquired_at=NOW,
    )
    second = normalize_candidate(
        {
            "url": "https://example.com/item?ref=feed",
            "title": "Second",
            "description": "Second description with different words.",
        },
        provider="two",
        acquired_at=NOW,
    )

    deduped = deduplicate_candidates([first, second])

    assert len(deduped) == 1
    assert deduped[0]["title"] == "First"
    assert deduped[0]["candidate_identity"] == "https://example.com/item"


def test_screen_candidate_is_deterministic_and_explains_eligibility():
    candidate = normalize_candidate(
        {
            "url": "https://openai.com/index/example",
            "title": "Documented model update",
            "description": (
                "Official release information describing concrete behavior, availability, "
                "and implementation details for decision makers."
            ),
            "published_at": "2026-10-13T12:00:00+00:00",
        },
        provider="OfficialVendor",
        acquired_at=NOW,
    )

    first = screen_candidate(candidate, now=NOW)
    second = screen_candidate(candidate, now=NOW)

    assert first == second
    assert isinstance(first["screening_score"], int)
    assert first["eligible"] is True
    assert first["screening_reasons"]
    assert all(isinstance(reason, str) for reason in first["screening_reasons"])


def test_rank_candidates_breaks_equal_scores_by_identity():
    a = normalize_candidate(
        {
            "url": "https://example.com/a",
            "title": "Same quality A",
            "description": "A description long enough to receive the same completeness score.",
        },
        provider="feed",
        acquired_at=NOW,
    )
    b = normalize_candidate(
        {
            "url": "https://example.com/b",
            "title": "Same quality B",
            "description": "B description long enough to receive the same completeness score.",
        },
        provider="feed",
        acquired_at=NOW,
    )

    ranked = rank_candidates([b, a], now=NOW)

    assert [item["candidate_identity"] for item in ranked] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_shadow_config_has_bounded_defaults():
    config = ShadowConfig()

    assert config.max_candidates_per_provider == 10
    assert config.max_deep_dive_attempts == 1
    assert config.min_screening_score == 40
