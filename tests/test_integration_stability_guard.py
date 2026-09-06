from __future__ import annotations

import unittest
from pathlib import Path

import integration_stability_guard as guard


ROOT = Path(__file__).resolve().parents[1]


class IntegrationStabilityGuardTests(unittest.TestCase):
    def test_current_repository_contract_is_green(self):
        self.assertEqual([], guard.collect_errors(ROOT))

    def test_workflow_rejects_broad_pytest_range(self):
        text = (ROOT / guard.INTEGRATION_WORKFLOW).read_text(encoding="utf-8")
        broken = text.replace(
            "pip install 'pytest==8.4.2' -c requirements-ci-constraints.txt",
            "pip install 'pytest>=8,<9'",
        )
        errors = guard.workflow_errors(broken)
        self.assertTrue(any("pytest" in error for error in errors))

    def test_run130_remote_counter_must_be_disabled_before_pipeline_import(self):
        text = (ROOT / guard.RUN130_TEST).read_text(encoding="utf-8")
        broken = text.replace(
            'os.environ.setdefault("GEMINI_PERSISTENT_DAILY_COUNTER", "false")\n',
            "",
        )
        errors = guard.run130_errors(broken)
        self.assertTrue(any("persistent remote Gemini counter" in error for error in errors))

    def test_runtime_manifest_copy_is_rejected(self):
        text = (ROOT / guard.RUNTIME_MANIFEST_TEST).read_text(encoding="utf-8")
        broken = "EXPECTED_RUNTIME_LAYER_ORDER = (\n    'x.install',\n)\n" + text
        errors = guard.runtime_manifest_test_errors(broken)
        self.assertTrue(any("duplicated" in error for error in errors))

    def test_network_guard_is_required(self):
        text = (ROOT / guard.NETWORK_GUARD).read_text(encoding="utf-8")
        broken = text.replace("@pytest.fixture(autouse=True)", "@pytest.fixture")
        errors = guard.network_guard_errors(broken)
        self.assertTrue(any("external-network" in error for error in errors))

    def test_known_green_top_level_pins_cannot_drift_silently(self):
        text = (ROOT / guard.CONSTRAINTS).read_text(encoding="utf-8")
        broken = text.replace("google-genai==1.75.0", "google-genai==1.76.0")
        errors = guard.constraints_errors(broken)
        self.assertTrue(any("google-genai==1.75.0" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
