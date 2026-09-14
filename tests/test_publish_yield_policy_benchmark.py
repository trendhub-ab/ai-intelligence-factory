from pathlib import Path

from publish_yield_benchmark import evaluate_benchmark, load_cases


FIXTURE = Path(__file__).parent / "fixtures" / "publish_yield_policy_benchmark_v1.json"


def test_publish_yield_policy_benchmark_has_zero_false_passes_and_zero_overholds():
    report = evaluate_benchmark(load_cases(FIXTURE))

    assert report["zero_provider_calls"] is True
    assert report["total_count"] == 13
    assert report["exact_match_count"] == 13
    assert report["exact_match_rate"] == 1.0
    assert report["safety_false_pass_count"] == 0
    assert report["core_false_pass_count"] == 0
    assert report["unnecessary_hold_count"] == 0

    # Three audited style-only classes should remain publishable under the current policy.
    assert report["projected_publishable_count"] == 3
    assert report["projected_publishable_yield"] == 3 / 13


def test_benchmark_fails_closed_if_a_core_case_is_accidentally_softened():
    cases = load_cases(FIXTURE)
    target = next(case for case in cases if case["id"] == "reader_core_without_companion")
    target["expected"] = "publishable"

    report = evaluate_benchmark(cases)
    assert report["unnecessary_hold_count"] == 1
    assert report["exact_match_count"] == 12


def test_benchmark_detects_a_safety_expectation_mismatch():
    cases = load_cases(FIXTURE)
    target = next(case for case in cases if case["id"] == "run51_fact_numeric")
    target["expected"] = "publishable"

    report = evaluate_benchmark(cases)
    assert report["unnecessary_hold_count"] == 1
    assert report["exact_match_count"] == 12
