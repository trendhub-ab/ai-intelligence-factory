from datetime import datetime, timezone
import inspect

import pytest

from v2_shadow_selection import (
    ShadowConfig,
    deduplicate_candidates,
    normalize_candidate,
    rank_candidates,
    run_shadow_selection,
    screen_candidate,
)


NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


def _raw_candidate(url, *, title="Candidate", description=None, published_at="2026-10-13T12:00:00+00:00"):
    return {
        "url": url,
        "title": title,
        "description": description
        if description is not None
        else "Concrete release evidence with enough detail for deterministic shadow screening and comparison.",
        "published_at": published_at,
    }


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


def test_shadow_run_bounds_candidates_and_isolates_provider_failure():
    deep_dive_calls = []

    def broken_provider():
        raise RuntimeError("provider unavailable")

    def good_provider():
        return [
            _raw_candidate("https://example.com/a", title="A"),
            _raw_candidate("https://example.com/b", title="B"),
            _raw_candidate("https://example.com/c", title="C"),
        ]

    def deep_dive(candidate):
        deep_dive_calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": True}

    report = run_shadow_selection(
        providers={"broken": broken_provider, "good": good_provider},
        deep_dive=deep_dive,
        config=ShadowConfig(max_candidates_per_provider=2),
        now=NOW,
        run_id="v2-001-bounded",
        v1_reference=None,
    )

    assert report["mode"] == "shadow"
    assert report["actual_calls"]["provider"] == 2
    assert report["provider_statuses"]["broken"]["status"] == "failure"
    assert report["provider_statuses"]["good"]["accepted_count"] == 2
    assert report["acquired_candidate_count"] == 2
    assert report["normalized_candidate_count"] == 2
    assert report["deep_dive_attempted_count"] == 1
    assert len(deep_dive_calls) == 1
    assert report["v2_selected_candidate_identity"] == deep_dive_calls[0]
    assert report["comparison_status"] == "unavailable"
    assert report["failure_category"] is None


def test_shadow_run_with_zero_eligible_candidates_skips_deep_dive():
    def provider():
        return [
            _raw_candidate(
                "https://example.com/thin",
                title="Thin",
                description="",
                published_at=None,
            )
        ]

    def should_not_run(_candidate):
        raise AssertionError("deep dive must not run")

    report = run_shadow_selection(
        providers={"feed": provider},
        deep_dive=should_not_run,
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-no-eligible",
        v1_reference="https://example.com/v1",
    )

    assert report["deep_dive_attempted_count"] == 0
    assert report["actual_calls"]["deep_dive"] == 0
    assert report["v2_selected_candidate_identity"] is None
    assert report["comparison_status"] == "v2_no_winner"
    assert report["failure_category"] == "insufficient_evidence"


def test_shadow_run_never_falls_back_to_second_candidate_after_insufficient_deep_dive():
    calls = []

    def provider():
        return [
            _raw_candidate("https://example.com/a", title="A"),
            _raw_candidate("https://example.com/b", title="B"),
        ]

    def insufficient(candidate):
        calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": False}

    report = run_shadow_selection(
        providers={"feed": provider},
        deep_dive=insufficient,
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-one-shot",
        v1_reference="https://example.com/a",
    )

    assert calls == ["https://example.com/a"]
    assert report["deep_dive_attempted_count"] == 1
    assert report["actual_calls"]["deep_dive"] == 1
    assert report["deep_dive_result_category"] == "insufficient_evidence"
    assert report["v2_selected_candidate_identity"] is None
    assert report["comparison_status"] == "v2_no_winner"
    assert report["failure_category"] == "insufficient_evidence"


@pytest.mark.parametrize(
    ("v1_reference", "expected_status"),
    [
        ("https://example.com/a?utm_source=v1", "same"),
        ("https://example.com/other", "different"),
        (None, "unavailable"),
    ],
)
def test_shadow_run_success_comparison_statuses(v1_reference, expected_status):
    report = run_shadow_selection(
        providers={"feed": lambda: [_raw_candidate("https://example.com/a", title="A")]},
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-compare",
        v1_reference=v1_reference,
    )

    assert report["v2_selected_candidate_identity"] == "https://example.com/a"
    assert report["comparison_status"] == expected_status
    assert report["failure_category"] is None


def test_shadow_report_contract_is_machine_readable_and_has_no_write_callbacks():
    signature = inspect.signature(run_shadow_selection)
    forbidden_params = {
        "persist",
        "writer",
        "notion",
        "note",
        "publish",
        "ready_state",
        "economic_state",
        "delivery_ledger",
    }
    assert forbidden_params.isdisjoint(signature.parameters)

    report = run_shadow_selection(
        providers={"official": lambda: [_raw_candidate("https://example.com/a", title="A")]},
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        config=ShadowConfig(max_candidates_per_provider=3, max_deep_dive_attempts=1, min_screening_score=40),
        now=NOW,
        run_id="v2-001-report",
    )

    assert report["run_id"] == "v2-001-report"
    assert report["timestamp"] == NOW.isoformat()
    assert report["mode"] == "shadow"
    assert report["provider_statuses"]["official"]["status"] == "success"
    assert report["deduplicated_candidate_count"] == 1
    assert report["screened_candidate_count"] == 1
    assert report["screening"][0]["candidate_identity"] == "https://example.com/a"
    assert report["budgets"] == {
        "max_candidates_per_provider": 3,
        "max_deep_dive_attempts": 1,
        "min_screening_score": 40,
    }
    assert report["actual_calls"] == {"provider": 1, "deep_dive": 1}
