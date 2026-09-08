from __future__ import annotations

import os
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock

import daily_portfolio_review as dpr
import product_review_runtime as prr


def _successful_child(*args, **kwargs):
    return SimpleNamespace(
        returncode=0,
        stdout="[PRODUCT REVIEW] observed\n",
        stderr="",
    )


def test_product_review_child_uses_provider_safe_entrypoint_and_runtime_counter():
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
    assert command == [sys.executable, "product_review_runtime.py"]
    env = captured["env"]
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
        returned = prr.install_product_review_provider_runtime(sentinel)

    assert returned is sentinel
    assert tuple(calls) == prr.PRODUCT_REVIEW_PROVIDER_LAYER_ORDER
    assert "run260_gemini_model_routing.install" not in calls
    assert "run172_production_reliability.install" not in calls


def test_provider_runtime_main_installs_before_pipeline_main():
    calls: list[str] = []

    fake_pipeline = SimpleNamespace(main=lambda: calls.append("pipeline.main"))

    def module(name: str):
        return SimpleNamespace(install=lambda pipeline: calls.append(name) or pipeline)

    fake_modules = {
        "pipeline": fake_pipeline,
        "run203_runtime_state_channel": module("run203_runtime_state_channel.install"),
        "gemini_timeout_rpd_fail_closed": module("gemini_timeout_rpd_fail_closed.install"),
        "gemini_transient_recovery": module("gemini_transient_recovery.install"),
        "gemini_provider_resilience": module("gemini_provider_resilience.install"),
    }
    with mock.patch.dict(sys.modules, fake_modules):
        prr.main()

    assert tuple(calls[:-1]) == prr.PRODUCT_REVIEW_PROVIDER_LAYER_ORDER
    assert calls[-1] == "pipeline.main"
