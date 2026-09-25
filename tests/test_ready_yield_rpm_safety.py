"""The canceled experiment must not send provider requests until RPM control exists."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "ready_yield_fixed_evidence.py"


class RpmSafetyTests(unittest.TestCase):
    def test_offline_preflight_checks_evidence_without_production_state(self):
        import tempfile
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--phase", "preflight", "--out-dir", out],
                text=True, capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(out) / "preflight.json").is_file())

    def test_live_phase_fails_closed_before_importing_provider_code(self):
        env = {**os.environ, "GEMINI_API_KEY": "dummy-for-zero-network-test"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--phase", "initial",
             "--model", "gemini-3.6-flash", "--out-dir", "/tmp/aiif-rpm-test"],
            env=env, text=True, capture_output=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RPM_SAFE_EXPERIMENT_DISABLED", result.stderr)


if __name__ == "__main__":
    unittest.main()
