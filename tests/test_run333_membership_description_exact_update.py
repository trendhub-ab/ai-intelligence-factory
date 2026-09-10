from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run333_membership_description_exact_update as run333

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "note-member-onboarding-membership-dialog-probe.yml").read_text(encoding="utf-8")


class Run333MembershipDescriptionExactUpdateTests(unittest.TestCase):
    def test_exact_target_copy_and_140_character_contract(self) -> None:
        self.assertEqual(run333.EDIT_URL, "https://note.com/membership/settings/plans/358b94bcb3c6/edit")
        self.assertEqual(run333.MEMBERSHIP_NAME, "AI Decision Intelligence")
        self.assertIn("AI Decision Intelligenceの利用方法", run333.OLD_DESCRIPTION)
        self.assertNotIn("AI Decision Intelligenceの利用方法", run333.NEW_DESCRIPTION)
        self.assertIn("最初にお読みください", run333.NEW_DESCRIPTION)
        self.assertLessEqual(len(run333.NEW_DESCRIPTION), run333.MAX_UI_CHARS)
        self.assertEqual(run333.MAX_UI_CHARS, 140)

    def test_only_description_is_filled_and_final_button_clicked_once(self) -> None:
        source = inspect.getsource(run333.update)
        self.assertIn("description.fill(NEW_DESCRIPTION)", source)
        self.assertIn("button.click()", source)
        self.assertIn("save_clicks += 1", source)
        self.assertIn("if save_clicks != 1", source)
        for forbidden in ("plan_name.fill", "fee.fill", "checkbox.click", "benefit.click"):
            self.assertNotIn(forbidden, source)
        self.assertEqual(run333.FINAL_BUTTON, "プランを変更する")

    def test_other_plan_controls_and_exact_benefits_are_preserved(self) -> None:
        snapshot = inspect.getsource(run333._other_plan_snapshot)
        source = inspect.getsource(run333.update)
        self.assertIn("form.querySelectorAll('input,textarea,select')", snapshot)
        self.assertIn("el === descriptionEl", snapshot)
        self.assertIn("checked", snapshot)
        self.assertIn("benefitLabels", snapshot)
        self.assertIn("特典を削除:", snapshot)
        self.assertIn("_require_other_settings_unchanged", source)
        self.assertIn("before save", source)
        self.assertIn("on fresh verification", source)

    def test_public_and_edit_states_are_fail_closed_and_idempotent(self) -> None:
        public_source = inspect.getsource(run333._public_description_state)
        edit_source = inspect.getsource(run333._open_exact_edit)
        source = inspect.getsource(run333.update)
        self.assertIn("OLD_DESCRIPTION", public_source)
        self.assertIn("NEW_DESCRIPTION", public_source)
        self.assertIn("run332.LEGACY_REFERENCE", public_source)
        self.assertIn("_description_state", edit_source)
        self.assertIn("public/edit description state mismatch", edit_source)
        self.assertIn('public_state == "current"', source)
        self.assertIn("already_current_verified_no_mutation", source)
        self.assertIn("updated_and_verified_exact_description_only", source)

    def test_live_workflow_is_manual_exact_and_zero_model(self) -> None:
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertIn("/aiif note membership description-update", WORKFLOW)
        self.assertIn(run333.CONFIRM_TOKEN, WORKFLOW)
        self.assertIn("run333_membership_description_exact_update.py", WORKFLOW)
        self.assertIn("tests.test_run333_membership_description_exact_update", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        upper = WORKFLOW.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
