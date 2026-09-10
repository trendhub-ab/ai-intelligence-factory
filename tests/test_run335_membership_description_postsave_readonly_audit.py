from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run333_membership_description_exact_update as run333
import run335_membership_description_postsave_readonly_audit as run335

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "note-membership-description-postsave-audit.yml"


class Run335MembershipDescriptionPostsaveReadonlyAuditTests(unittest.TestCase):
    def test_exact_target_and_dual_state_classification(self) -> None:
        self.assertEqual(run335.CONFIRM_TOKEN, "AUDIT_MEMBERSHIP_DESCRIPTION_POSTSAVE_RUN335_READONLY")
        self.assertIn("legacy", inspect.getsource(run335._public_state))
        self.assertIn("current", inspect.getsource(run335._public_state))
        self.assertIn("unexpected", inspect.getsource(run335._public_state))
        self.assertEqual(run333.MEMBERSHIP_NAME, "AI Decision Intelligence")
        self.assertEqual(run333.EXPECTED_FEE_MARKER, "1,980 円/月")

    def test_audit_is_zero_click_zero_fill_zero_save(self) -> None:
        source = inspect.getsource(run335.audit)
        self.assertNotIn(".click(", source)
        self.assertNotIn(".fill(", source)
        self.assertNotIn("insert_text", source)
        self.assertNotIn("keyboard.type", source)
        self.assertIn('"clicks_performed": 0', source)
        self.assertIn('"field_filled": False', source)
        self.assertIn('"save_clicked": False', source)
        self.assertIn('"membership_mutation": False', source)
        self.assertIn('"public_mutation": False', source)
        self.assertIn('"zero_gemini_calls": True', source)
        self.assertIn('"notion_writes": 0', source)

    def test_form_audit_preserves_exact_plan_fee_and_benefits(self) -> None:
        source = inspect.getsource(run335.audit)
        self.assertIn("run333.EXPECTED_PLAN_NAME", inspect.getsource(run335._exact_plan_name))
        self.assertIn("run333.EXPECTED_FEE_MARKER", source)
        self.assertIn("run334._other_plan_snapshot", source)
        self.assertIn("run333.EXPECTED_BENEFITS", source)
        self.assertIn("public_edit_consistent", source)

    def test_workflow_is_manual_read_only_and_zero_model(self) -> None:
        self.assertTrue(WORKFLOW_PATH.exists())
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("/aiif note membership description-audit", workflow)
        self.assertIn(run335.CONFIRM_TOKEN, workflow)
        self.assertIn("run335_membership_description_postsave_readonly_audit.py", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)
        upper = workflow.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
