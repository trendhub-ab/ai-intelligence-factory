from datetime import datetime, timezone

from v2_shadow_selection import ShadowConfig, run_shadow_selection


NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


def _candidate(url: str, title: str = "Candidate") -> dict:
    return {
        "url": url,
        "title": title,
        "description": (
            "Concrete evidence with enough detail for deterministic shadow screening, "
            "ranking, and bounded Deep Dive evaluation."
        ),
        "published_at": "2026-10-13T12:00:00+00:00",
    }


def test_all_provider_failure_is_structured_and_does_not_leak_error_message():
    def broken_provider():
        raise RuntimeError("SECRET_PROVIDER_DETAIL")

    report = run_shadow_selection(
        providers={"broken": broken_provider},
        deep_dive=lambda _candidate: (_ for _ in ()).throw(
            AssertionError("deep dive must not run")
        ),
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-all-provider-failure",
        v1_reference="https://example.com/v1",
    )

    assert report["provider_statuses"]["broken"] == {
        "status": "failure",
        "accepted_count": 0,
        "normalized_count": 0,
        "rejected_count": 0,
        "error_category": "RuntimeError",
    }
    assert report["acquired_candidate_count"] == 0
    assert report["normalized_candidate_count"] == 0
    assert report["deep_dive_attempted_count"] == 0
    assert report["actual_calls"] == {"provider": 1, "deep_dive": 0}
    assert report["v2_selected_candidate_identity"] is None
    assert report["comparison_status"] == "v2_no_winner"
    assert report["failure_category"] == "all_providers_failed"
    assert "SECRET_PROVIDER_DETAIL" not in repr(report)


def test_malformed_provider_candidate_fails_closed_without_deep_dive():
    report = run_shadow_selection(
        providers={"feed": lambda: [{"description": "missing URL and title"}]},
        deep_dive=lambda _candidate: (_ for _ in ()).throw(
            AssertionError("deep dive must not run")
        ),
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-malformed-candidate",
    )

    assert report["provider_statuses"]["feed"]["status"] == "success"
    assert report["provider_statuses"]["feed"]["accepted_count"] == 1
    assert report["provider_statuses"]["feed"]["normalized_count"] == 0
    assert report["provider_statuses"]["feed"]["rejected_count"] == 1
    assert report["deep_dive_attempted_count"] == 0
    assert report["v2_selected_candidate_identity"] is None
    assert report["comparison_status"] == "v2_no_winner"
    assert report["failure_category"] == "insufficient_evidence"


def test_deep_dive_provider_failure_is_one_shot_and_never_falls_back():
    calls = []

    def deep_dive(candidate):
        calls.append(candidate["candidate_identity"])
        raise TimeoutError("provider timeout detail")

    report = run_shadow_selection(
        providers={
            "feed": lambda: [
                _candidate("https://example.com/a", "A"),
                _candidate("https://example.com/b", "B"),
            ]
        },
        deep_dive=deep_dive,
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-001-deep-dive-failure",
    )

    assert calls == ["https://example.com/a"]
    assert report["deep_dive_attempted_count"] == 1
    assert report["actual_calls"]["deep_dive"] == 1
    assert report["deep_dive_result_category"] == "provider_failure"
    assert report["failure_category"] == "deep_dive_failure"
    assert report["v2_selected_candidate_identity"] is None
    assert report["comparison_status"] == "v2_no_winner"
    assert "provider timeout detail" not in repr(report)
