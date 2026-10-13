from v2_shadow_selection_fixture import build_fixture_report


def _collect_keys(value):
    keys = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(_collect_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            keys.update(_collect_keys(nested))
    return keys


def test_provider_free_fixture_proves_bounded_shadow_selection_without_mutation():
    first = build_fixture_report()
    second = build_fixture_report()

    assert first == second
    assert first["mode"] == "shadow"
    assert first["deep_dive_attempted_count"] == 1
    assert first["actual_calls"]["deep_dive"] == 1
    assert first["actual_calls"]["provider"] == 2
    assert first["deduplicated_candidate_count"] == 2
    assert first["v2_selected_candidate_identity"] == "https://vendor.example.com/releases/alpha"
    assert first["comparison_status"] == "different"
    assert first["failure_category"] is None

    forbidden = {
        "notion",
        "note",
        "publish",
        "ready_state",
        "economic_state",
        "delivery_ledger",
    }
    assert forbidden.isdisjoint(_collect_keys(first))
