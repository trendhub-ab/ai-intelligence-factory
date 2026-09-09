from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run320_member_onboarding_membership_dialog_probe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-membership-dialog-probe.yml").read_text(encoding="utf-8") if (ROOT / ".github/workflows/note-member-onboarding-membership-dialog-probe.yml").exists() else ""


class Run320MembershipDialogProbeTests(unittest.TestCase):
    def test_exact_target_and_server_saved_source_only(self):
        self.assertIn('MENU_ACTION_LABEL = "メンバーシップ特典追加・解除"', SCRIPT)
        self.assertIn("run315.NEW_TITLE", SCRIPT)
        self.assertIn("run317.NEW_BODY_SHA256", SCRIPT)
        self.assertIn("run315._verify_editor(body)", SCRIPT)
        self.assertIn("fresh_cookie_only_context", SCRIPT)
        self.assertIn("local_storage_seeded", SCRIPT)

    def test_only_exact_menu_action_is_opened(self):
        self.assertIn('_visible_exact(page, role="menuitem", name=MENU_ACTION_LABEL)', SCRIPT)
        self.assertIn("menu_action.click()", SCRIPT)
        self.assertNotIn('name="追加"', SCRIPT)
        self.assertNotIn('name="追加する"', SCRIPT)
        self.assertNotIn('name="保存"', SCRIPT)
        self.assertNotIn('name="保存する"', SCRIPT)
        self.assertNotIn('name="更新する"', SCRIPT)

    def test_probe_explicitly_reports_no_mutation(self):
        self.assertIn('"membership_selection_clicked": False', SCRIPT)
        self.assertIn('"final_confirm_clicked": False', SCRIPT)
        self.assertIn('"membership_mutation": False', SCRIPT)
        self.assertIn('"public_mutation": False', SCRIPT)
        self.assertIn('"zero_gemini_calls": True', SCRIPT)
        self.assertIn('"notion_writes": 0', SCRIPT)

    def test_workflow_is_exact_and_zero_model(self):
        self.assertIn("PROBE_MEMBER_ONBOARDING_MEMBERSHIP_DIALOG_N284E428C80F4_SHAAAB9E57B", WORKFLOW)
        self.assertIn("/aiif note onboarding membership-probe", WORKFLOW)
        self.assertIn("tests.test_run320_member_onboarding_membership_dialog_probe", WORKFLOW)
        self.assertIn("run320_member_onboarding_membership_dialog_probe.py", WORKFLOW)
        self.assertNotIn("GEMINI", WORKFLOW.upper())
        self.assertNotIn("NOTION_API", WORKFLOW.upper())


if __name__ == "__main__":
    unittest.main()
