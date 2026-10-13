from __future__ import annotations

from tests.v2_shadow_observation_fixture import build_fixture_report
from v2_shadow_observation import write_observation


def test_fixture_observes_both_sources_with_zero_deep_dive_and_no_winner():
    report = build_fixture_report()

    assert report["provider_statuses"]["HackerNews"]["status"] == "success"
    assert report["provider_statuses"]["ArXiv"]["status"] == "success"
    assert report["acquired_candidate_count"] == 4
    assert report["screened_candidate_count"] == 4
    assert report["deep_dive_attempted_count"] == 0
    assert report["actual_calls"]["deep_dive"] == 0
    assert report["v2_selected_candidate_identity"] is None
    assert report["pre_deep_dive_leader"] is not None
    assert report["observation"]["mode"] == "manual_zero_model"


def test_fixture_serialization_is_byte_stable_for_fixed_input_time_and_run_id(tmp_path):
    first = build_fixture_report()
    second = build_fixture_report()
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    write_observation(first, first_path)
    write_observation(second, second_path)

    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()
