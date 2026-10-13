from __future__ import annotations

from tests.v2_live_shadow_acquisition_fixture import run_fixture


def test_fixture_flows_both_sources_through_v2_001_with_one_deep_dive():
    report, deep_dive_calls = run_fixture()

    assert report["mode"] == "shadow"
    assert report["provider_statuses"]["HackerNews"]["status"] == "success"
    assert report["provider_statuses"]["ArXiv"]["status"] == "success"
    assert report["acquired_candidate_count"] == 4
    assert report["normalized_candidate_count"] == 4
    assert report["deduplicated_candidate_count"] == 4
    assert report["screened_candidate_count"] == 4
    assert report["deep_dive_attempted_count"] == 1
    assert len(deep_dive_calls) == 1
    assert report["v2_selected_candidate_identity"] == deep_dive_calls[0]
    assert report["comparison_status"] == "different"
    assert report["live_acquisition"] == {
        "sources": ["HackerNews", "ArXiv"],
        "http_method": "GET",
        "hn_limit": 2,
        "arxiv_limit": 2,
        "total_candidate_limit": 4,
        "timeout_seconds": 2.0,
    }


def test_fixture_is_deterministic_for_fixed_input_and_time():
    first_report, first_calls = run_fixture()
    second_report, second_calls = run_fixture()

    assert first_report == second_report
    assert first_calls == second_calls
    assert first_report["deep_dive_attempted_count"] <= 1
