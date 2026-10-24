"""P5 live API proofs must never run merely because a PR branch advanced.

A P5 proof experiment on 2026-10-24 was inadvertently re-triggered
by unrelated pull_request synchronize commits. This provider-free guard
refuses any future P5 secret-bearing workflow with an automatic trigger.
"""
from pathlib import Path
import re

import pytest


AUTO_EVENTS = (
    "pull_request",
    "pull_request_target",
    "push",
    "schedule",
    "workflow_run",
    "issue_comment",
    "issues",
)


def assert_manually_triggered_p5_workflow(name: str, yaml: str) -> None:
    """Inspect P5 model API workflows; never execute an API call."""
    if not name.startswith("p5-") or "GEMINI_API_KEY" not in yaml:
        return
    if not re.search(r"(?m)^  workflow_dispatch\s*:", yaml):
        raise ValueError("P5 API proof requires explicit manual workflow_dispatch")
    for event in AUTO_EVENTS:
        if re.search(r"(?m)^  " + re.escape(event) + r"\s*:", yaml):
            raise ValueError(f"P5 API proof forbids automatic trigger {event}")
    if "github.run_attempt == 1" not in yaml:
        raise ValueError("P5 API proof requires run_attempt=1")
    if "concurrency:" not in yaml or "ai-intelligence-gemini-budget" not in yaml:
        raise ValueError("P5 API proof requires canonical Gemini concurrency")


def test_repo_has_no_automatically_triggered_p5_live_api_workflow():
    root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    for file in (*root.glob("*.yml"), *root.glob("*.yaml")):
        assert_manually_triggered_p5_workflow(file.name, file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("event", AUTO_EVENTS)
def test_p5_workflow_rejects_auto_trigger_even_if_manual_also_present(event: str):
    unsafe = (
        "name: P5 API Proof\n"
        "on:\n"
        "  workflow_dispatch:\n"
        f"  {event}:\n"
        "permissions:\n  contents: read\n"
        "concurrency:\n  group: ai-intelligence-gemini-budget\n"
        "jobs:\n"
        "  proof:\n"
        "    if: github.run_attempt == 1\n"
        "    steps:\n"
        "      - run: echo $GEMINI_API_KEY\n"
    )
    with pytest.raises(ValueError, match="forbids automatic trigger"):
        assert_manually_triggered_p5_workflow("p5-unsafe.yml", unsafe)


def test_p5_requires_manual_run_guard_and_serial_gemini_budget():
    base = (
        "name: P5 API Proof\n"
        "on:\n  workflow_dispatch:\n"
        "jobs:\n  proof:\n"
        "    steps:\n      - run: echo $GEMINI_API_KEY\n"
    )
    with pytest.raises(ValueError, match="run_attempt"):
        assert_manually_triggered_p5_workflow("p5-one-time.yml", base)
    with pytest.raises(ValueError, match="concurrency"):
        assert_manually_triggered_p5_workflow(
            "p5-one-time.yml", base + "    if: github.run_attempt == 1\n",
        )


def test_non_p5_workflows_are_not_redefined_by_experiment_guard():
    # Existing production workflows retain their unchanged authorities.
    assert_manually_triggered_p5_workflow(
        "daily-one-shot.yml", "on:\n  schedule:\n  - cron: '5 8 * * *'\nGEMINI_API_KEY",
    )
