from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest

import production_pipeline
import run231_performance_telemetry as perf
import runtime_layers


EXPECTED_RUNTIME_LAYER_ORDER = (
    "run203_runtime_state_channel.install",
    "gemini_timeout_rpd_fail_closed.install",
    "gemini_transient_recovery.install",
    "run172_production_reliability.install",
    "run173_operational_yield.install",
    "run174_monthly_digest_integrity.install",
    "run175_semantic_fact_precision.install",
    "run223_technical_claim_precision.install",
    "run224_multiplier_deterministic_rescue.install",
    "run227_japanese_surface_integrity.install",
    "run176_scope_fidelity.install",
    "run177_paid_funnel_alignment.install",
    "run226_reader_delight_planning.install",
    "run228_reader_rhythm_planning.install",
    "run178_eyecatch_editorial_layout_optimizer.install",
    "run179_eyecatch_font_refinement.install",
    "run180_eyecatch_semantic_layout.install",
    "run181_eyecatch_visual_balance.install",
    "run182_eyecatch_conclusion_emphasis.install",
    "run183_eyecatch_emphasis_scale.install",
    "reader_value_review_bridge.install",
    "run208_reader_value_repair.install",
    "run222_note_presentation_integrity.install_pipeline",
    "run194_publication_contract.install",
)


def _fake_runtime_modules(events):
    modules = {}
    for spec in EXPECTED_RUNTIME_LAYER_ORDER:
        module_name, function_name = spec.rsplit(".", 1)
        module = types.ModuleType(module_name)

        def installer(pipeline_module, _spec=spec):
            events.append(_spec)
            return pipeline_module

        setattr(module, function_name, installer)
        modules[module_name] = module
    return modules


def test_runtime_layer_order_contract_is_exact_and_executable():
    assert runtime_layers.RUNTIME_LAYER_ORDER == EXPECTED_RUNTIME_LAYER_ORDER

    events = []
    fake_modules = _fake_runtime_modules(events)
    sentinel_pipeline = object()
    with patch.dict(sys.modules, fake_modules, clear=False):
        returned = runtime_layers.install_runtime_layers(sentinel_pipeline)

    assert returned is sentinel_pipeline
    assert tuple(events) == EXPECTED_RUNTIME_LAYER_ORDER


def test_performance_wrapper_preserves_args_return_and_single_call(monkeypatch):
    monkeypatch.setattr(perf, "ENABLED", True)
    calls = []
    sentinel = object()

    class Logger:
        def info(self, *args, **kwargs):
            pass

    pipeline = types.SimpleNamespace(logger=Logger())

    def initialize_runtime(*args, **kwargs):
        calls.append((args, kwargs))
        return sentinel

    def main():
        return "main-result"

    pipeline.initialize_runtime = initialize_runtime
    pipeline.main = main

    telemetry = perf.install(pipeline)
    result = pipeline.initialize_runtime(1, 2, mode="safe")

    assert result is sentinel
    assert calls == [((1, 2), {"mode": "safe"})]
    assert telemetry.calls["runtime.initialize"] == 1
    assert pipeline.main() == "main-result"


def test_performance_wrapper_propagates_same_exception(monkeypatch):
    monkeypatch.setattr(perf, "ENABLED", True)
    error = RuntimeError("unchanged")

    class Logger:
        def info(self, *args, **kwargs):
            pass

    pipeline = types.SimpleNamespace(logger=Logger())

    def initialize_runtime():
        raise error

    pipeline.initialize_runtime = initialize_runtime
    pipeline.main = lambda: None
    telemetry = perf.install(pipeline)

    with pytest.raises(RuntimeError) as caught:
        pipeline.initialize_runtime()

    assert caught.value is error
    assert telemetry.calls["runtime.initialize"] == 1
    assert telemetry.failures["runtime.initialize"] == 1


def test_performance_install_is_idempotent(monkeypatch):
    monkeypatch.setattr(perf, "ENABLED", True)

    class Logger:
        def info(self, *args, **kwargs):
            pass

    calls = []
    pipeline = types.SimpleNamespace(logger=Logger())
    pipeline.initialize_runtime = lambda: calls.append("called")
    pipeline.main = lambda: None

    first = perf.install(pipeline)
    wrapped_first = pipeline.initialize_runtime
    second = perf.install(pipeline)

    assert first is second
    assert pipeline.initialize_runtime is wrapped_first
    pipeline.initialize_runtime()
    assert calls == ["called"]


def test_production_entrypoint_keeps_setup_before_observability(monkeypatch):
    events = []

    fake_pipeline = types.ModuleType("pipeline")
    fake_pipeline.SYNTHETIC_REGRESSION_MODE = False
    fake_pipeline.logger = object()
    fake_pipeline.main = lambda: events.append("pipeline.main")

    runtime_state = types.ModuleType("run203_runtime_state_channel")
    runtime_state.preflight_runtime_state_channel = lambda: events.append("preflight")

    font = types.ModuleType("run179_eyecatch_font_refinement")
    font.ensure_google_font_assets = lambda **kwargs: events.append(("font", kwargs["enabled"]))

    telemetry = types.ModuleType("run231_performance_telemetry")
    telemetry.install = lambda pipeline_module: events.append("telemetry")

    monkeypatch.setattr(
        production_pipeline,
        "install_runtime_layers",
        lambda pipeline_module: events.append("runtime_layers") or pipeline_module,
    )

    with patch.dict(
        sys.modules,
        {
            "pipeline": fake_pipeline,
            "run203_runtime_state_channel": runtime_state,
            "run179_eyecatch_font_refinement": font,
            "run231_performance_telemetry": telemetry,
        },
        clear=False,
    ):
        production_pipeline.main()

    assert events == [
        "runtime_layers",
        "preflight",
        ("font", True),
        "telemetry",
        "pipeline.main",
    ]
