import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import production_pipeline
import run231_performance_telemetry as perf


ROOT = Path(__file__).resolve().parents[1]


class _QuietLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


class Run231PipelineSlimTests(unittest.TestCase):
    def test_runtime_layer_order_contract_is_single_source_semantic_and_executable(self):
        import runtime_layers

        declared = tuple(runtime_layers.RUNTIME_LAYER_ORDER)
        self.assertTrue(declared)
        self.assertEqual(len(declared), len(set(declared)))
        self.assertEqual(declared[-1], "run194_publication_contract.install")

        source = (ROOT / "runtime_layers.py").read_text(encoding="utf-8")
        self.assertIn("def install_runtime_layers(pipeline_module):", source)
        self.assertIn("RUNTIME_LAYER_ORDER = (", source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("exec(", source)

        production = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("from runtime_layers import install_runtime_layers as _canonical_install_runtime_layers", production)
        self.assertIn("install_runtime_layers = _canonical_install_runtime_layers", production)

    def test_performance_install_is_idempotent(self):
        pipeline = types.SimpleNamespace(logger=_QuietLogger())
        pipeline.main = lambda: "ok"
        pipeline.generate_intelligence_report = lambda *a, **k: {"ok": True}
        pipeline.screen_candidates = lambda *a, **k: []
        pipeline.fetch_all_candidates = lambda *a, **k: []

        with patch.object(perf, "ENABLED", True):
            perf.install(pipeline)
            first_main = pipeline.main
            perf.install(pipeline)
            self.assertIs(first_main, pipeline.main)

    def test_performance_wrapper_preserves_args_return_and_single_call(self):
        calls = []
        pipeline = types.SimpleNamespace(logger=_QuietLogger())

        def fn(*args, **kwargs):
            calls.append((args, kwargs))
            return {"sentinel": object()}

        pipeline.main = fn
        pipeline.generate_intelligence_report = lambda *a, **k: None
        pipeline.screen_candidates = lambda *a, **k: None
        pipeline.fetch_all_candidates = lambda *a, **k: None

        with patch.object(perf, "ENABLED", True):
            perf.install(pipeline)
            result = pipeline.main(1, two=2)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ((1,), {"two": 2}))
        self.assertIsInstance(result, dict)
        self.assertIn("sentinel", result)

    def test_performance_wrapper_propagates_same_exception(self):
        original = RuntimeError("boom")
        pipeline = types.SimpleNamespace(logger=_QuietLogger())

        def fn():
            raise original

        pipeline.main = fn
        pipeline.generate_intelligence_report = lambda *a, **k: None
        pipeline.screen_candidates = lambda *a, **k: None
        pipeline.fetch_all_candidates = lambda *a, **k: None

        with patch.object(perf, "ENABLED", True):
            perf.install(pipeline)
            with self.assertRaises(RuntimeError) as caught:
                pipeline.main()
        self.assertIs(caught.exception, original)

    def test_broken_logger_cannot_change_successful_production_return(self):
        sentinel = object()

        class BrokenLogger:
            def info(self, *args, **kwargs):
                raise RuntimeError("logger down")

            warning = error = info

        pipeline = types.SimpleNamespace(logger=BrokenLogger())
        pipeline.main = lambda: sentinel
        pipeline.generate_intelligence_report = lambda *a, **k: None
        pipeline.screen_candidates = lambda *a, **k: None
        pipeline.fetch_all_candidates = lambda *a, **k: None

        with patch.object(perf, "ENABLED", True):
            perf.install(pipeline)
            self.assertIs(pipeline.main(), sentinel)

    def test_broken_logger_cannot_mask_original_production_exception(self):
        original = ValueError("production")

        class BrokenLogger:
            def info(self, *args, **kwargs):
                raise RuntimeError("logger down")

            warning = error = info

        pipeline = types.SimpleNamespace(logger=BrokenLogger())

        def fail():
            raise original

        pipeline.main = fail
        pipeline.generate_intelligence_report = lambda *a, **k: None
        pipeline.screen_candidates = lambda *a, **k: None
        pipeline.fetch_all_candidates = lambda *a, **k: None

        with patch.object(perf, "ENABLED", True):
            perf.install(pipeline)
            with self.assertRaises(ValueError) as caught:
                pipeline.main()
        self.assertIs(caught.exception, original)

    def test_record_failure_cannot_change_wrapped_return_or_exception(self):
        sentinel = object()
        original = LookupError("original")
        pipeline = types.SimpleNamespace(logger=_QuietLogger())
        pipeline.main = lambda: None
        pipeline.generate_intelligence_report = lambda *a, **k: None
        pipeline.screen_candidates = lambda *a, **k: None
        pipeline.fetch_all_candidates = lambda *a, **k: None

        with patch.object(perf, "ENABLED", True), patch.object(
            perf, "_record", side_effect=RuntimeError("record failure")
        ):
            perf.install(pipeline)

            def successful():
                return sentinel

            def failing():
                raise original

            wrapped_success = perf._wrap("successful", successful, pipeline.logger)
            wrapped_failure = perf._wrap("failing", failing, pipeline.logger)

        self.assertIs(wrapped_success(), sentinel)
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

        numeric_precision = types.ModuleType("run283_numeric_evidence_equivalence")
        numeric_precision.install = lambda pipeline_module: events.append("run283") or pipeline_module

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
                "run283_numeric_evidence_equivalence": numeric_precision,
            },
            clear=False,
        ):
            production_pipeline.main()

        self.assertEqual(
            events,
            [
                "runtime_layers",
                "run283",
                "preflight",
                ("font", True),
                "telemetry",
                "pipeline.main",
            ],
        )


if __name__ == "__main__":
    unittest.main()
