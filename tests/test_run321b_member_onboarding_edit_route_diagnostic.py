from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run321b_member_onboarding_edit_route_diagnostic.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-official-edit-route-probe.yml").read_text(encoding="utf-8")
CHATOPS = (ROOT / ".github/workflows/chatops-note.yml").read_text(encoding="utf-8")


class Run321bEditRouteDiagnosticTests(unittest.TestCase):
    def test_exact_source_and_target(self):
        self.assertIn("run317.NEW_BODY_SHA256", SCRIPT)
        self.assertIn("run315.NEW_TITLE", SCRIPT)
        self.assertIn("run319.ARTICLE_LIST_URL", SCRIPT)
        self.assertIn("run319._mark_target_card(page)", SCRIPT)
        self.assertIn("run319._open_menu_if_exact(page, card)", SCRIPT)
        self.assertIn('name=run321.EDIT_LABEL).click()', SCRIPT)

    def test_diagnostic_records_intermediate_ui_and_does_not_guess(self):
        self.assertIn('"after_edit": after_edit', SCRIPT)
        self.assertIn('"exact_labels_after_edit": exact_labels_after_edit', SCRIPT)
        self.assertIn('"after_version_choice": after_version_choice', SCRIPT)
        self.assertIn('"editor_route_reached":', SCRIPT)
        self.assertIn("run321._maybe_choose_latest_draft(page)", SCRIPT)
        self.assertNotIn('run310._unique_button(page, "公開に進む")', SCRIPT)

    def test_no_mutation_contract(self):
        for marker in (
            '"final_commit_clicked": False',
            '"content_mutation": False',
            '"settings_mutation": False',
            '"membership_mutation": False',
            '"public_mutation": False',
            '"zero_gemini_calls": True',
            '"notion_writes": 0',
        ):
            self.assertIn(marker, SCRIPT)

    def test_reuses_existing_hard_bound_workflow_and_chatops(self):
        token = "PROBE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_N284E428C80F4_SHAAAB9E57B"
        self.assertIn("CONFIRM_TOKEN = run321.CONFIRM_TOKEN", SCRIPT)
        self.assertIn(token, WORKFLOW)
        self.assertIn("run321b_member_onboarding_edit_route_diagnostic.py", WORKFLOW)
        self.assertIn("tests.test_run321b_member_onboarding_edit_route_diagnostic", WORKFLOW)
        self.assertIn("/aiif note onboarding edit-route-probe", CHATOPS)
        self.assertIn("note-member-onboarding-official-edit-route-probe.yml", CHATOPS)
        self.assertIn(token, CHATOPS)
        upper = (WORKFLOW + CHATOPS).upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
