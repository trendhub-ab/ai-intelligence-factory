from __future__ import annotations

import math

import pytest

from v2_semantic_screening import (
    GoldBenchmarkContractError,
    SEMANTIC_FIELDS,
    evaluate_gold_predictions,
    validate_gold_dataset,
)


def _case(case_id: str, gold: dict[str, bool]):
    return {
        "case_id": case_id,
        "title": f"title {case_id}",
        "description": f"description {case_id}",
        "source_family": "fixture",
        "gold": gold,
        "rationale": "human-reviewed fixture rationale",
        "label_provenance": "v2_semantic_contract_2026-10-17",
    }


def _vector(ai: bool, decision: bool, novelty: bool, applied: bool):
    return {
        "ai_relevant": ai,
        "decision_value": decision,
        "change_novelty": novelty,
        "applied_reader_value": applied,
    }


def _dataset(cases):
    return {
        "benchmark_version": "v1",
        "label_contract": "v2_semantic_screening",
        "cases": cases,
    }


def test_gold_dataset_validation_is_strict_and_rejects_integer_booleans_and_duplicate_ids():
    valid = _dataset([
        _case("a", _vector(True, True, False, False)),
        _case("b", _vector(False, False, False, False)),
    ])
    rows = validate_gold_dataset(valid)
    assert [row["case_id"] for row in rows] == ["a", "b"]
    assert SEMANTIC_FIELDS == (
        "ai_relevant",
        "decision_value",
        "change_novelty",
        "applied_reader_value",
    )

    bad_bool = _dataset([_case("a", {**_vector(True, True, False, False), "decision_value": 1})])
    with pytest.raises(GoldBenchmarkContractError):
        validate_gold_dataset(bad_bool)

    duplicate = _dataset([
        _case("a", _vector(True, False, False, False)),
        _case("a", _vector(False, False, False, False)),
    ])
    with pytest.raises(GoldBenchmarkContractError):
        validate_gold_dataset(duplicate)


def test_evaluator_reports_exact_confusion_matrices_macro_metrics_and_saturation():
    cases = validate_gold_dataset(_dataset([
        _case("a", _vector(True, True, True, True)),
        _case("b", _vector(True, False, True, False)),
        _case("c", _vector(False, False, False, False)),
        _case("d", _vector(True, True, False, False)),
    ]))
    predictions = {
        "a": _vector(True, True, True, True),
        "b": _vector(True, True, False, False),
        "c": _vector(False, False, False, False),
        "d": _vector(False, True, False, False),
    }

    report = evaluate_gold_predictions(cases, predictions)

    assert report["sample_count"] == 4
    assert report["dimensions"]["ai_relevant"] == {
        "tp": 2,
        "fp": 0,
        "tn": 1,
        "fn": 1,
        "precision": pytest.approx(1.0),
        "recall": pytest.approx(2 / 3),
        "f1": pytest.approx(0.8),
    }
    assert report["dimensions"]["decision_value"]["tp"] == 2
    assert report["dimensions"]["decision_value"]["fp"] == 1
    assert report["dimensions"]["change_novelty"]["tp"] == 1
    assert report["dimensions"]["change_novelty"]["fn"] == 1
    assert report["exact_match_accuracy"] == pytest.approx(0.5)
    assert report["all_positive_saturation_rate"] == pytest.approx(0.25)

    expected_macro_precision = sum(
        report["dimensions"][field]["precision"] for field in SEMANTIC_FIELDS
    ) / 4
    assert report["macro"]["precision"] == pytest.approx(expected_macro_precision)
    assert all(not math.isnan(report["macro"][name]) for name in ("precision", "recall", "f1"))


def test_zero_denominator_metrics_are_zero_not_nan():
    cases = validate_gold_dataset(_dataset([
        _case("a", _vector(False, False, False, False)),
        _case("b", _vector(False, False, False, False)),
    ]))
    predictions = {
        "a": _vector(False, False, False, False),
        "b": _vector(False, False, False, False),
    }

    report = evaluate_gold_predictions(cases, predictions)
    for field in SEMANTIC_FIELDS:
        assert report["dimensions"][field]["precision"] == 0.0
        assert report["dimensions"][field]["recall"] == 0.0
        assert report["dimensions"][field]["f1"] == 0.0


def test_prediction_contract_fails_closed_on_missing_extra_or_non_boolean_fields():
    cases = validate_gold_dataset(_dataset([
        _case("a", _vector(True, False, False, False)),
        _case("b", _vector(False, False, False, False)),
    ]))

    with pytest.raises(GoldBenchmarkContractError):
        evaluate_gold_predictions(cases, {"a": _vector(True, False, False, False)})

    with pytest.raises(GoldBenchmarkContractError):
        evaluate_gold_predictions(
            cases,
            {
                "a": _vector(True, False, False, False),
                "b": _vector(False, False, False, False),
                "extra": _vector(False, False, False, False),
            },
        )

    bad = _vector(True, False, False, False)
    bad["decision_value"] = 1
    with pytest.raises(GoldBenchmarkContractError):
        evaluate_gold_predictions(
            cases,
            {"a": bad, "b": _vector(False, False, False, False)},
        )
