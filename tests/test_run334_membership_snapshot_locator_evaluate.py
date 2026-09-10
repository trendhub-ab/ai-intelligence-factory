from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run333_membership_description_exact_update as run333
import run334_membership_description_exact_update as run334

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "note-member-onboarding-membership-dialog-probe.yml").read_text(encoding="utf-8")


class Run334MembershipSnapshotLocatorEvaluateTests(unittest.TestCase):
    def test_snapshot_uses_locator_evaluate_not_page_evaluate(self) -> None:
        source = inspect.getsource(run334._other_plan_snapshot)
        self.assertIn("description.evaluate(", source)
        self.assertNotIn("page.evaluate(", source)
        self.assertIn("descriptionEl.closest('form')", source)
        self.assertIn("form.querySelectorAll('input,textarea,select')", source)
        self.assertIn("benefitLabels", source)

    def test_run334_changes_only_failed_snapshot_function(self) -> None:
        source = inspect.getsource(run334.update)
        self.assertIn("run333._other_plan_snapshot = _other_plan_snapshot", source)
        self.assertIn("result = run333.update()", source)
        self.assertIn("run333._other_plan_snapshot = original_snapshot", source)
        self.assertEqual(run333.NEW_DESCRIPTION.count("最初にお読みください"), 1)
        self.assertEqual(run333.FINAL_BUTTON, "プランを変更する")

    def test_exact_authorization_is_new_and_inner_contract_remains_hard_bound(self) -> None:
        source = inspect.getsource(run334.update)
        self.assertEqual(
            run334.CONFIRM_TOKEN,
            "UPDATE_MEMBERSHIP_DESCRIPTION_AI_DECISION_INTELLIGENCE_RUN334_EXACT",
        )
        self.assertIn("NOTE_MEMBERSHIP_DESCRIPTION_RUN334_CONFIRM", source)
        self.assertIn("run333.CONFIRM_TOKEN", source)
        self.assertIn("NOTE_MEMBERSHIP_DESCRIPTION_RUN333_CONFIRM", source)

    def test_live_workflow_advances_to_run334_only(self) -> None:
        self.assertIn("/aiif note membership description-update", WORKFLOW)
        self.assertIn(run334.CONFIRM_TOKEN, WORKFLOW)
        self.assertIn("run334_membership_description_exact_update.py", WORKFLOW)
        self.assertIn("tests.test_run334_membership_snapshot_locator_evaluate", WORKFLOW)
        self.assertNotIn("xvfb-run -a python run333_membership_description_exact_update.py", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        upper = WORKFLOW.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
