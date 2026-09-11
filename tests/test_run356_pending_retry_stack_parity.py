from __future__ import annotations

import inspect

import pending_retry_validation as fast_lane
import production_pipeline


PRODUCTION_OVERLAY_CALLS = (
    "install_source_normalization",
    "install_runtime_layers",
    "install_run349_score_narrative_negation_precision",
    "install_run283_numeric_evidence_equivalence",
    "install_run268_business_source_strategy",
    "install_run269_business_source_precision",
    "install_reader_quality_precision",
    "install_run284_reader_recovery_precision",
    "install_run287_publication_date_provenance",
    "install_performance_telemetry",
)


def _positions(source: str, names: tuple[str, ...]) -> list[int]:
    positions = []
    for name in names:
        pos = source.find(name + "(")
        assert pos >= 0, f"missing Production overlay call: {name}"
        positions.append(pos)
    return positions


def test_fast_lane_installs_current_production_article_overlays_in_same_order():
    production_source = inspect.getsource(production_pipeline.main)
    fast_lane_source = inspect.getsource(fast_lane.install_current_production_article_stack)

    production_positions = _positions(production_source, PRODUCTION_OVERLAY_CALLS)
    fast_lane_positions = _positions(fast_lane_source, PRODUCTION_OVERLAY_CALLS)

    assert production_positions == sorted(production_positions)
    assert fast_lane_positions == sorted(fast_lane_positions)


def test_fast_lane_budget_is_explicit_three_request_cap():
    assert fast_lane.FAST_LANE_PENDING_RETRY_REQUEST_BUDGET == 3
    env = {}
    fast_lane.prepare_fast_lane_env(env)
    assert env["GEMINI_PENDING_RETRY_REQUEST_BUDGET"] == "3"
    assert env[fast_lane.FAST_LANE_ENV] == "1"


def test_fast_lane_does_not_install_full_run_backlog_or_fresh_acquisition_overlay():
    source = inspect.getsource(fast_lane.install_current_production_article_stack)
    assert "install_run346_backlog_budget_reserve" not in source
    assert "install_full_recovery" not in source
