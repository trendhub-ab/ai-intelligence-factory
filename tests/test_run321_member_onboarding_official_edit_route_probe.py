from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run321_member_onboarding_official_edit_route_probe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-official-edit-route-probe.yml").read_text(encoding="utf-8") if (ROOT / ".github/workflows/note-member-onboarding-official-edit-route-probe.yml").exists() else ""
CHATOPS = (ROOT / ".github/workflows/chatops-note.yml").read_text(encoding="utf-8")


class Run321OfficialEditRouteProbeTests(unittest.TestCase):
    def test_exact_server_saved_source_and_official_list_edit_route(self):
        self.assertIn("run317.NEW_BODY_SHA256", SCRIPT)
        self.assertIn("run319.ARTICLE_LIST_URL", SCRIPT)
        self.assertIn("run319._mark_target_card(page)", SCRIPT)
        self.assertIn("run319._open_menu_if_exact(page, card)", SCRIPT)
        self.assertIn('_visible_exact(page, role="menuitem", name=EDIT_LABEL).click()', SCRIPT)
        self.assertIn('EDIT_LABEL = "編集"', SCRIPT)

    def test_latest_draft_choice_is_navigation_only(self):
        self.assertIn('LATEST_DRAFT_LABEL = "最新の下書き"', SCRIPT)
        self.assertIn("_maybe_choose_latest_draft(page)", SCRIPT)
        self.assertIn("run315.NEW_TITLE", SCRIPT)
        self.assertIn("run315._verify_editor(body)", SCRIPT)

    def test_probe_enters_publish_settings_but_never_commits(self):
        self.assertIn('run310._unique_button(page, "公開に進む").click()', SCRIPT)
        self.assertIn('"final_commit_clicked": False', SCRIPT)
        self.assertIn('"content_mutation": False', SCRIPT)
        self.assertIn('"settings_mutation": False', SCRIPT)
        self.assertIn('"membership_mutation": False', SCRIPT)
        self.assertIn('"public_mutation": False', SCRIPT)
        self.assertNotIn('"更新する").click()', SCRIPT)
        self.assertNotIn('"公開する").click()', SCRIPT)

    def test_workflow_and_chatops_are_hard_bound_and_zero_model(self):
        token = "PROBE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_N284E428C80F4_SHAAAB9E57B"
        self.assertIn(token, WORKFLOW)
        self.assertIn("tests.test_run321_member_onboarding_official_edit_route_probe", WORKFLOW)
        self.assertIn("run321_member_onboarding_official_edit_route_probe.py", WORKFLOW)
        self.assertIn("/aiif note onboarding edit-route-probe", CHATOPS)
        self.assertIn("note-member-onboarding-official-edit-route-probe.yml", CHATOPS)
        self.assertIn(token, CHATOPS)
        upper = (WORKFLOW + CHATOPS).upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
