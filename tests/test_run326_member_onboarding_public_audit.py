from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run326_member_onboarding_public_audit.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-public-audit.yml").read_text(encoding="utf-8")
CHATOPS = (ROOT / ".github/workflows/chatops-note.yml").read_text(encoding="utf-8")


class Run326MemberOnboardingPublicAuditTests(unittest.TestCase):
    def test_exact_public_target_and_current_title_are_hard_bound(self):
        self.assertIn("run315.TARGET_PUBLIC_URL", SCRIPT)
        self.assertIn("run315.TARGET_NOTE_ID", SCRIPT)
        self.assertIn("run315.NEW_TITLE", SCRIPT)
        self.assertIn("run315.AUDITED_TITLE", SCRIPT)
        self.assertIn("run317._launch_clean_browser", SCRIPT)

    def test_audit_is_fresh_logged_out_and_never_seeds_state(self):
        self.assertIn("browser.new_context", SCRIPT)
        self.assertIn("if context.cookies():", SCRIPT)
        self.assertIn('"fresh_no_cookie_context": True', SCRIPT)
        self.assertNotIn("add_cookies", SCRIPT)
        self.assertNotIn("storage_state", SCRIPT)
        self.assertNotIn("_seed_note_state", SCRIPT)
        self.assertNotIn("_launch_persistent_context", SCRIPT)

    def test_no_click_or_mutation_paths_exist(self):
        self.assertNotIn(".click()", SCRIPT)
        self.assertNotIn(".fill(", SCRIPT)
        self.assertNotIn(".press(", SCRIPT)
        self.assertNotIn(".set_input_files(", SCRIPT)
        self.assertNotIn("公開に進む", SCRIPT)
        self.assertNotIn("更新する", SCRIPT)
        self.assertNotIn("一時保存", SCRIPT)
        for marker in (
            '"clicks_performed": 0',
            '"content_mutation": False',
            '"settings_mutation": False',
            '"membership_mutation": False',
            '"public_mutation": False',
        ):
            self.assertIn(marker, SCRIPT)

    def test_customer_facing_postconditions_are_fail_closed(self):
        self.assertIn("NOT_FOR_SALE_MARKERS", SCRIPT)
        self.assertIn("PROTECTED_BODY_MARKERS", SCRIPT)
        self.assertIn("GATE_MARKERS", SCRIPT)
        self.assertIn("BOT_OR_CHALLENGE_MARKERS", SCRIPT)
        self.assertIn("if not new_title_visible", SCRIPT)
        self.assertIn("if old_title_visible", SCRIPT)
        self.assertIn("if protected_hits", SCRIPT)
        self.assertIn("if not gate_hits", SCRIPT)
        self.assertIn('"members_only_gate_verified": True', SCRIPT)

    def test_workflow_and_chatops_are_manual_zero_model_read_only(self):
        token = "AUDIT_PUBLIC_MEMBER_ONBOARDING_N284E428C80F4_SHAAAB9E57B_LOGGED_OUT"
        self.assertIn(token, SCRIPT)
        self.assertIn(token, WORKFLOW)
        self.assertIn(token, CHATOPS)
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        self.assertIn("run326_member_onboarding_public_audit.py", WORKFLOW)
        self.assertIn("tests.test_run326_member_onboarding_public_audit", WORKFLOW)
        self.assertIn("/aiif note onboarding public-audit", CHATOPS)
        self.assertIn("note-member-onboarding-public-audit.yml", CHATOPS)
        upper = WORKFLOW.upper() + CHATOPS.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
