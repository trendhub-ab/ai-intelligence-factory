from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "note-profile-update.yml").read_text(encoding="utf-8")


class Run331ProfileWorkflowContractTests(unittest.TestCase):
    def test_run331_regression_is_in_preflight_and_runner(self) -> None:
        self.assertIn("tests.test_run331_profile_form_snapshot_scope", WORKFLOW)
        self.assertIn("Run330/331", WORKFLOW)

    def test_mutation_token_and_script_are_unchanged(self) -> None:
        self.assertIn("UPDATE_NOTE_PROFILE_TRENDHUB_BIZ_RUN330_EXACT_BIOGRAPHY", WORKFLOW)
        self.assertIn("xvfb-run -a python run330_note_profile_exact_update.py", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
