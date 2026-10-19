"""CI regression tests must not inherit unrelated workflow_dispatch inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import production_pipeline


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def manual_dispatch_without_inputs(monkeypatch, tmp_path):
    event = tmp_path / "workflow-dispatch.json"
    event.write_text(json.dumps({"inputs": None}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.delenv("AIIF_ONE_SHOT_MODE", raising=False)
    return event


def test_pipeline_order_unit_contract_isolated_from_manual_dispatch(manual_dispatch_without_inputs):
    from tests.test_run231_pipeline_slim import Run231PipelineSlimTests

    test = Run231PipelineSlimTests(
        "test_production_entrypoint_keeps_setup_before_observability_without_legacy_reimport"
    )
    test.test_production_entrypoint_keeps_setup_before_observability_without_legacy_reimport()


def test_product_review_unit_contract_isolated_from_manual_dispatch(manual_dispatch_without_inputs):
    from tests.test_run305_product_review_provider_runtime import (
        test_main_selects_product_review_runtime_before_article_stack,
    )

    test_main_selects_product_review_runtime_before_article_stack()


def test_synthetic_smoke_does_not_inherit_manual_dispatch_input():
    workflow = (
        ROOT / ".github/workflows/integration-reconciliation-ci.yml"
    ).read_text(encoding="utf-8")
    smoke = workflow.split("- name: Run synthetic smoke through current Production stack", 1)[1]
    assert "run: env -u GITHUB_EVENT_PATH -u AIIF_ONE_SHOT_MODE python production_pipeline.py" in smoke


def test_actual_dispatch_mode_still_rejects_nonobject_inputs(manual_dispatch_without_inputs):
    with pytest.raises(RuntimeError, match="Invalid ONE-SHOT dispatch inputs"):
        production_pipeline._workflow_dispatch_mode()
