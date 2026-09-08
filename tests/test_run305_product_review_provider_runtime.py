from __future__ import annotations

import os
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock

import daily_portfolio_review as dpr
import production_pipeline as pp


def _successful_child(*args, **kwargs):
    return SimpleNamespace(
        returncode=0,
        stdout="[PRODUCT REVIEW] observed\n",
        stderr="",
    )


def test_product_review_child_uses_production_entrypoint_and_runtime_counter():
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["env"] = dict(kwargs["env"])
        return _successful_child()

    with mock.patch.dict(
        os.environ,
        {
            "AIIF_RUNTIME_STATE_BRANCH": "runtime-state",
            "GEMINI_COUNTER_BRANCH": "main",
        },
        clear=False,
    ), mock.patch.object(subprocess, "run", side_effect=fake_run):
        result = dpr._run_product_only(["entity:test"], 1, 1, timeout=1)

    assert result["returncode"] == 0
    command = captured["args"][0]
    assert command == [sys.executable, "production_pipeline.py"]
    env = captured["env"]
    assert env["AIIF_PRODUCT_REVIEW_RUNTIME"] == "true"
    assert env["GEMINI_COUNTER_BRANCH"] == "runtime-state"


def test_provider_runtime_installs_only_required_layers_in_order():
    calls: list[str] = []

    def module(name: str):
        return SimpleNamespace(install=lambda pipeline: calls.append(name) or pipeline)

    fake_modules = {
        "run203_runtime_state_channel": module("run203_runtime_state_channel.install"),
        "gemini_timeout_rpd_fail_closed": module("gemini_timeout_rpd_fail_closed.install"),
        "gemini_transient_recovery": module("gemini_transient_recovery.install"),
        "gemini_provider_resilience": module("gemini_provider_resilience.install"),
    }
    sentinel = object()
    with mock.patch.dict(sys.modules, fake_modules):
        returned = pp.install_product_review_provider_runtime(sentinel)

    assert returned is sentinel
    assert tuple(calls) == pp.PRODUCT_REVIEW_PROVIDER_LAYER_ORDER
    assert "run260_gemini_model_routing.install" not in calls
    assert "run172_production_reliability.install" not in calls


def test_product_review_runtime_installs_preflights_then_runs_pipeline():
    calls: list[str] = []
    fake_pipeline = SimpleNamespace(
        SYNTHETIC_REGRESSION_MODE=False,
        main=lambda: calls.append("pipeline.main"),
    )

    def module(name: str):
        return SimpleNamespace(
            install=lambda pipeline: calls.append(name) or pipeline,
            preflight_runtime_state_channel=lambda: calls.append("runtime.preflight"),
        )

    fake_modules = {
        "pipeline": fake_pipeline,
        "run203_runtime_state_channel": module("run203_runtime_state_channel.install"),
        "gemini_timeout_rpd_fail_closed": module("gemini_timeout_rpd_fail_closed.install"),
        "gemini_transient_recovery": module("gemini_transient_recovery.install"),
        "gemini_provider_resilience": module("gemini_provider_resilience.install"),
    }
    with mock.patch.dict(sys.modules, fake_modules):
        pp._run_product_review_runtime()

    assert tuple(calls[:4]) == pp.PRODUCT_REVIEW_PROVIDER_LAYER_ORDER
    assert calls[4:] == ["runtime.preflight", "pipeline.main"]


def test_main_selects_product_review_runtime_before_article_stack():
    with mock.patch.dict(os.environ, {"AIIF_PRODUCT_REVIEW_RUNTIME": "true"}, clear=False), \
         mock.patch.object(pp, "_run_product_review_runtime") as run_product_review:
        pp.main()
    run_product_review.assert_called_once_with()
