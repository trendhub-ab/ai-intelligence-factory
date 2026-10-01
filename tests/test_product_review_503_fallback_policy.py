from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import daily_portfolio_review as dpr
import inventory_bootstrap


def test_product_only_environment_sets_full_product_review_model_pool():
    env = inventory_bootstrap.product_only_environment(2, 3)

    assert env["GEMINI_DEEP_DIVE_MODEL_CANDIDATES"] == (
        "gemini-3.6-flash,gemini-3.7-flash,gemini-3.8-flash,gemini-3.5-flash"
    )
    assert env["PRODUCT_REVIEW_MAX_PER_RUN"] == "2"
    assert env["GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET"] == "3"


def _child(stdout: str):
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def test_product_only_503_uses_next_distinct_model_instead_of_same_model_retry():
    runs = [
        _child(
            "[PROVIDER HTTP 503] model=gemini-3.6-flash kind=product_review attempt=1/2 verified=structured_status\n"
            "[PRODUCT REVIEW] {'attempted': 1, 'saved': 0}\n"
        ),
        _child("[PRODUCT REVIEW] {'attempted': 1, 'saved': 1}\n"),
    ]
    captured_envs = []

    def fake_run(*args, **kwargs):
        captured_envs.append(dict(kwargs["env"]))
        return runs.pop(0)

    with mock.patch.object(dpr.subprocess, "run", side_effect=fake_run):
        result = dpr._run_product_only(["entity:a"], 1, 3, timeout=1)

    assert [e["GEMINI_DEEP_DIVE_MODEL_CANDIDATES"] for e in captured_envs] == [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
    ]
    assert all(e["GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET"] == "1" for e in captured_envs)
    assert result["model_attempts"] == 2
    assert result["saved_reviews"] == 1


def test_product_only_budget_three_can_reach_three_distinct_models():
    runs = [
        _child(
            "[PROVIDER HTTP 503] model=gemini-3.6-flash kind=product_review attempt=1/2 verified=structured_status\n"
            "[PRODUCT REVIEW] {'attempted': 1, 'saved': 0}\n"
        ),
        _child(
            "[PROVIDER HTTP 503] model=gemini-3.7-flash kind=product_review attempt=1/2 verified=structured_status\n"
            "[PRODUCT REVIEW] {'attempted': 1, 'saved': 0}\n"
        ),
        _child("[PRODUCT REVIEW] {'attempted': 1, 'saved': 1}\n"),
    ]
    captured_envs = []

    def fake_run(*args, **kwargs):
        captured_envs.append(dict(kwargs["env"]))
        return runs.pop(0)

    with mock.patch.object(dpr.subprocess, "run", side_effect=fake_run):
        result = dpr._run_product_only(["entity:a"], 1, 3, timeout=1)

    assert [e["GEMINI_DEEP_DIVE_MODEL_CANDIDATES"] for e in captured_envs] == [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
    ]
    assert result["model_attempts"] == 3
    assert result["saved_reviews"] == 1


def test_product_only_stops_after_total_request_budget_without_fourth_model():
    runs = [
        _child(
            f"[PROVIDER HTTP 503] model={model} kind=product_review attempt=1/2 verified=structured_status\n"
            "[PRODUCT REVIEW] {'attempted': 1, 'saved': 0}\n"
        )
        for model in ("gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash")
    ]
    captured_envs = []

    def fake_run(*args, **kwargs):
        captured_envs.append(dict(kwargs["env"]))
        return runs.pop(0)

    with mock.patch.object(dpr.subprocess, "run", side_effect=fake_run):
        result = dpr._run_product_only(["entity:a"], 1, 3, timeout=1)

    assert [e["GEMINI_DEEP_DIVE_MODEL_CANDIDATES"] for e in captured_envs] == [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
    ]
    assert result["model_attempts"] == 3
    assert result["saved_reviews"] == 0
    assert result["request_budget"] == 3
