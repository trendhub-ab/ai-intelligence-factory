from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import production_pipeline
import run231_performance_telemetry as perf
import runtime_layers


def _fake_runtime_modules(events):
    modules = {}
    for spec in runtime_layers.RUNTIME_LAYER_ORDER:
        module_name, function_name = spec.rsplit(".", 1)
        module = types.ModuleType(module_name)

        def installer(pipeline_module, _spec=spec):
            events.append(_spec)
            return pipeline_module

        setattr(module, function_name, installer)
        modules[module_name] = module
    return modules


class _QuietLogger:
    def info(self, *args, **kwargs):
        pass


class _RaisingLogger:
    def info(self, *args, **kwargs):
        raise RuntimeError("telemetry logger failed")


class Run231PipelineSlimTests(unittest.TestCase):
    def test_runtime_layer_order_contract_is_single_source_semantic_and_executable(self):
        order = runtime_layers.RUNTIME_LAYER_ORDER
        self.assertTrue(order)
        self.assertEqual(len(order), len(set(order)), "runtime layer manifest contains duplicates")
        self.assertEqual(order[0], "run203_runtime_state_channel.install")
        self.assertEqual(order[-1], "run194_publication_contract.install")
        self.assertTrue(all("." in spec and spec.rsplit(".", 1)[1] for spec in order))

        def assert_before(first, second):
            self.assertIn(first, order)
            self.assertIn(second, order)
            self.assertLess(order.index(first), order.index(second))

        assert_before(
            "gemini_timeout_rpd_fail_closed.install",
            "gemini_transient_recovery.install",
        )
        assert_before(
            "gemini_transient_recovery.install",
            "run260_gemini_model_routing.install",
        )
        assert_before(
            "run226_reader_delight_planning.install",
            "run228_reader_rhythm_planning.install",
        )
        assert_before(
            "run248_first_real_publish_quality_calibration.install",
            "run249_final_publication_surface_gate.install",
        )
        assert_before(
            "run249_final_publication_surface_gate.install",
            "run194_publication_contract.install",
        )

        events = []
        fake_modules = _fake_runtime_modules(events)
        sentinel_pipeline = object()
        with patch.dict(sys.modules, fake_modules, clear=False):
            returned = runtime_layers.install_runtime_layers(sentinel_pipeline)

        self.assertIs(returned, sentinel_pipeline)
        self.assertEqual(tuple(events), order)

    def test_performance_wrapper_preserves_args_return_and_single_call(self):
        calls = []
        sentinel = object()
        pipeline = types.SimpleNamespace(logger=_QuietLogger())

        def initialize_runtime(*args, **kwargs):
            calls.append((args, kwargs))
            return sentinel

        pipeline.initialize_runtime = initialize_runtime
        pipeline.main = lambda: "main-result"

        with patch.object(perf, "ENABLED", True):
            telemetry = perf.install(pipeline)
            result = pipeline.initialize_runtime(1, 2, mode="safe")

        self.assertIs(result, sentinel)
        self.assertEqual(calls, [((1, 2), {"mode": "safe"})])
        self.assertEqual(telemetry.calls["runtime.initialize"], 1)
        self.assertEqual(pipeline.main(), "main-result")

    def test_performance_wrapper_propagates_same_exception(self):
        error = RuntimeError("unchanged")
        pipeline = types.SimpleNamespace(logger=_QuietLogger())

        def initialize_runtime():
            raise error

        pipeline.initialize_runtime = initialize_runtime
        pipeline.main = lambda: None

        with patch.object(perf, "ENABLED", True):
            telemetry = perf.install(pipeline)
            with self.assertRaises(RuntimeError) as caught:
                pipeline.initialize_runtime()

        self.assertIs(caught.exception, error)
        self.assertEqual(telemetry.calls["runtime.initialize"], 1)
        self.assertEqual(telemetry.failures["runtime.initialize"], 1)

    def test_performance_install_is_idempotent(self):
        calls = []
        pipeline = types.SimpleNamespace(logger=_QuietLogger())
        pipeline.initialize_runtime = lambda: calls.append("called")
        pipeline.main = lambda: None

        with patch.object(perf, "ENABLED", True):
            first = perf.install(pipeline)
            wrapped_first = pipeline.initialize_runtime
            second = perf.install(pipeline)

        self.assertIs(first, second)
        self.assertIs(pipeline.initialize_runtime, wrapped_first)
        pipeline.initialize_runtime()
        self.assertEqual(calls, ["called"])

    def test_broken_logger_cannot_change_successful_production_return(self):
        sentinel = object()
        pipeline = types.SimpleNamespace(logger=_RaisingLogger())
        pipeline.initialize_runtime = lambda: sentinel
        pipeline.main = lambda: "main-ok"

        with patch.object(perf, "ENABLED", True):
            perf.install(pipeline)
            self.assertIs(pipeline.initialize_runtime(), sentinel)
            self.assertEqual(pipeline.main(), "main-ok")

    def test_broken_logger_cannot_mask_original_production_exception(self):
        original = ValueError("original production failure")
        pipeline = types.SimpleNamespace(logger=_RaisingLogger())
        pipeline.main = lambda: (_ for _ in ()).throw(original)

        with patch.object(perf, "ENABLED", True):
            perf.install(pipeline)
            with self.assertRaises(ValueError) as caught:
                pipeline.main()

        self.assertIs(caught.exception, original)

    def test_record_failure_cannot_change_wrapped_return_or_exception(self):
        success = object()
        original = LookupError("original")
        telemetry = perf.PerformanceTelemetry(_QuietLogger())

        def broken_record(*args, **kwargs):
            raise RuntimeError("telemetry record failed")

        telemetry.record = broken_record
        wrapped_success = perf._wrap(telemetry, lambda: success, "stage")
        wrapped_failure = perf._wrap(
            telemetry,
            lambda: (_ for _ in ()).throw(original),
            "stage",
        )

        self.assertIs(wrapped_success(), success)
        with self.assertRaises(LookupError) as caught:
            wrapped_failure()
        self.assertIs(caught.exception, original)

    def test_control_flow_exception_is_not_reclassified_or_swallowed(self):
        pipeline = types.SimpleNamespace(logger=_QuietLogger())
        pipeline.main = lambda: (_ for _ in ()).throw(SystemExit(7))

        with patch.object(perf, "ENABLED", True):
            perf.install(pipeline)
            with self.assertRaises(SystemExit) as caught:
                pipeline.main()

        self.assertEqual(caught.exception.code, 7)

    def test_production_entrypoint_keeps_setup_before_observability_without_legacy_reimport(self):
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

        with patch.object(
            production_pipeline,
            "install_runtime_layers",
            lambda pipeline_module: events.append("runtime_layers") or pipeline_module,
        ), patch.dict(
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

        self.assertEqual(
            events,
            [
                "runtime_layers",
                "preflight",
                ("font", True),
                "telemetry",
                "pipeline.main",
            ],
        )


if __name__ == "__main__":
    unittest.main()
