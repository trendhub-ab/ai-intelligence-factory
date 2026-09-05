from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

RETIRED_TIMING_ARTIFACTS = (
    "perf_timing.py",
    "pipeline_timing_probe.py",
    "RUN231_PERFORMANCE_DIAGNOSTICS.md",
)

RETIRED_TIMING_TESTS = (
    "tests/test_run231_no_default_timing_side_effect.py",
    "tests/test_run231_perf_timing.py",
    "tests/test_run231_perf_timing_contract.py",
    "tests/test_run231_pipeline_timing_probe.py",
    "tests/test_run231_timing_average.py",
    "tests/test_run231_timing_empty_emit.py",
    "tests/test_run231_timing_json_shape.py",
    "tests/test_run231_timing_multiple_names.py",
    "tests/test_run231_timing_record_clamp.py",
    "tests/test_run231_timing_reset.py",
    "tests/test_run231_timing_rounding.py",
    "tests/test_run231_timing_snapshot_copy.py",
    "tests/test_run231_timing_summary_sort.py",
    "tests/test_run231_timing_threadsafe_shape.py",
)


class Run233CICollectionIntegrityTests(unittest.TestCase):
    def test_current_performance_telemetry_is_single_canonical_path(self):
        telemetry = ROOT / "run231_performance_telemetry.py"
        production = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        self.assertTrue(telemetry.is_file())
        self.assertIn(
            "from run231_performance_telemetry import install as install_performance_telemetry",
            production,
        )
        self.assertIn("install_runtime_layers(pipeline)", production)
        self.assertIn("install_performance_telemetry(pipeline)", production)
        self.assertLess(
            production.index("install_runtime_layers(pipeline)"),
            production.index("install_performance_telemetry(pipeline)"),
        )

    def test_redundant_timing_utility_probe_docs_and_tests_stay_retired(self):
        for relative in (*RETIRED_TIMING_ARTIFACTS, *RETIRED_TIMING_TESTS):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_full_integration_regression_uses_pytest_collection(self):
        workflow = (
            ROOT / ".github/workflows/integration-reconciliation-ci.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("pip install 'pytest>=8,<9'", workflow)
        self.assertIn("python -m pytest -q tests", workflow)
        self.assertNotIn(
            "python -m unittest discover -s tests -v > full-unittest.log",
            workflow,
        )

    def test_stage2_temporary_compatibility_workflow_stays_retired(self):
        self.assertFalse(
            (ROOT / ".github/workflows/run231-stage2-surgical-migration.yml").exists()
        )


if __name__ == "__main__":
    unittest.main()
