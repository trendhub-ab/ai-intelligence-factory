from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace
from unittest import mock

import daily_portfolio_review as dpr


def _successful_child(*args, **kwargs):
    return SimpleNamespace(
        returncode=0,
        stdout="[PRODUCT REVIEW] observed\n",
        stderr="",
    )


def test_product_only_child_prefers_authoritative_runtime_state_branch():
    captured: dict[str, str] = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs["env"])
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
    assert captured["GEMINI_COUNTER_BRANCH"] == "runtime-state"


def test_product_only_child_preserves_operator_branch_without_runtime_overlay():
    captured: dict[str, str] = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs["env"])
        return _successful_child()

    with mock.patch.dict(
        os.environ,
        {"GEMINI_COUNTER_BRANCH": "operator-branch"},
        clear=False,
    ), mock.patch.object(subprocess, "run", side_effect=fake_run):
        os.environ.pop("AIIF_RUNTIME_STATE_BRANCH", None)
        result = dpr._run_product_only(["entity:test"], 1, 1, timeout=1)

    assert result["returncode"] == 0
    assert captured["GEMINI_COUNTER_BRANCH"] == "operator-branch"


def test_zero_budget_skips_without_spawning_child():
    with mock.patch.object(subprocess, "run") as run:
        result = dpr._run_product_only(["entity:test"], 1, 0, timeout=1)
    assert result["skipped"] is True
    assert result["reason"] == "no_due_candidates_or_budget"
    run.assert_not_called()
