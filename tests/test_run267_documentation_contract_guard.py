from __future__ import annotations

import unittest
from pathlib import Path

import run267_documentation_contract_guard as guard


ROOT = Path(__file__).resolve().parents[1]


class Run267DocumentationContractGuardTests(unittest.TestCase):
    def test_current_repository_contract_is_green(self):
        self.assertEqual([], guard.collect_errors(ROOT))

    def test_stale_run209_functional_baseline_is_rejected(self):
        spec = (ROOT / guard.SPEC).read_text(encoding="utf-8")
        broken = spec.replace(
            "Core Reliability Baseline: **Run209",
            "現行Functional Baseline: **Run209",
            1,
        )
        errors = guard.spec_errors(broken)
        self.assertTrue(any("stale_marker" in error or "Core Reliability" in error for error in errors))

    def test_stale_run181_eyecatch_baseline_is_rejected(self):
        spec = (ROOT / guard.SPEC).read_text(encoding="utf-8")
        broken = spec.replace("Eyecatch Baseline: **Run183", "Eyecatch Baseline: **Run181 current**", 1)
        errors = guard.spec_errors(broken)
        self.assertTrue(any("stale_marker" in error or "Eyecatch Baseline" in error for error in errors))

    def test_production_pillow_floor_cannot_drift_silently(self):
        requirements = (ROOT / guard.REQUIREMENTS).read_text(encoding="utf-8")
        constraints = (ROOT / guard.CONSTRAINTS).read_text(encoding="utf-8")
        spec = (ROOT / guard.SPEC).read_text(encoding="utf-8")
        broken = requirements.replace("Pillow>=12.1.0,<13.0.0", "Pillow>=11.3.0,<13.0.0")
        errors = guard.dependency_errors(broken, constraints, spec)
        self.assertTrue(any("pillow_range" in error for error in errors))

    def test_required_check_path_filter_is_rejected(self):
        integration = (ROOT / guard.INTEGRATION).read_text(encoding="utf-8")
        broken = integration.replace(
            "    branches:\n      - main\n",
            "    branches:\n      - main\n    paths:\n      - 'pipeline.py'\n",
            1,
        )
        errors = guard.required_check_errors(
            {"zero-api-regression": (guard.INTEGRATION, broken)}
        )
        self.assertTrue(any("path_filter" in error for error in errors))

    def test_required_context_job_name_is_protected(self):
        integration = (ROOT / guard.INTEGRATION).read_text(encoding="utf-8")
        broken = integration.replace("  zero-api-regression:\n", "  zero-api-regression-renamed:\n", 1)
        errors = guard.required_check_errors(
            {"zero-api-regression": (guard.INTEGRATION, broken)}
        )
        self.assertTrue(any("job_context_missing" in error for error in errors))

    def test_run183_scale_contract_is_protected(self):
        runtime = (ROOT / guard.RUNTIME_LAYERS).read_text(encoding="utf-8")
        scale = (ROOT / guard.EYECATCH_SCALE).read_text(encoding="utf-8")
        spec = (ROOT / guard.SPEC).read_text(encoding="utf-8")
        broken = scale.replace("HIGHLIGHT_FONT_SCALE = 1.20", "HIGHLIGHT_FONT_SCALE = 1.00")
        errors = guard.eyecatch_errors(runtime, broken, spec)
        self.assertTrue(any("scale_contract_missing" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
