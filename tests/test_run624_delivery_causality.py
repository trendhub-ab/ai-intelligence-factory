from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"


class Run624DeliveryCausalityTests(unittest.TestCase):
    def test_full_mode_must_gate_private_draft_on_current_run_ready_count(self) -> None:
        source = ONE_SHOT.read_text(encoding="utf-8")
        self.assertIn("run624_delivery_causality.py", source)
        self.assertIn('create_private_draft="$create_private_draft"', source)

    def test_zero_ready_disables_private_draft_but_keeps_reconciliation(self) -> None:
        mod = importlib.import_module("run624_delivery_causality")
        with tempfile.TemporaryDirectory() as td:
            summary = Path(td) / "RUN_SUMMARY.md"
            summary.write_text(
                "# Daily Article Audit Summary\n\n"
                "| Candidate | Source | Decision Score | Final Status | Disposition | Quality Warnings / Failure Reason | Markdown |\n"
                "|---|---|---:|---|---|---|---|\n"
                "| a | GitHub | 80 | PENDING_RETRY | retry | provider unavailable | x.md |\n",
                encoding="utf-8",
            )
            decision = mod.delivery_decision(summary)
        self.assertEqual(decision["ready_count"], 0)
        self.assertFalse(decision["create_private_draft"])
        self.assertTrue(decision["run_note_reconciliation"])

    def test_current_run_ready_enables_private_draft(self) -> None:
        mod = importlib.import_module("run624_delivery_causality")
        with tempfile.TemporaryDirectory() as td:
            summary = Path(td) / "RUN_SUMMARY.md"
            summary.write_text(
                "# Daily Article Audit Summary\n\n"
                "| Candidate | Source | Decision Score | Final Status | Disposition | Quality Warnings / Failure Reason | Markdown |\n"
                "|---|---|---:|---|---|---|---|\n"
                "| a | GitHub | 80 | READY | publish |  | articles/ready/a/final.md |\n",
                encoding="utf-8",
            )
            decision = mod.delivery_decision(summary)
        self.assertEqual(decision["ready_count"], 1)
        self.assertTrue(decision["create_private_draft"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
