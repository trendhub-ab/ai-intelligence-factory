from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = (ROOT / "run321b_member_onboarding_edit_route_diagnostic.py").read_text(encoding="utf-8")
RUN322 = (ROOT / "run322_member_onboarding_version_confirm_publish_probe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-official-edit-route-probe.yml").read_text(encoding="utf-8")
CHATOPS = (ROOT / ".github/workflows/chatops-note.yml").read_text(encoding="utf-8")


class Run321bEditRouteDiagnosticTests(unittest.TestCase):
    def test_wrapper_reuses_exact_authorization_and_delegates_to_run322(self):
        self.assertIn("CONFIRM_TOKEN = run321.CONFIRM_TOKEN", WRAPPER)
        self.assertIn("import run322_member_onboarding_version_confirm_publish_probe as run322", WRAPPER)
        self.assertIn("result = run322.probe()", WRAPPER)
        self.assertIn('result["status"] = "diagnostic_complete_no_mutation"', WRAPPER)
        self.assertIn('result["run322_probe_completed"] = True', WRAPPER)

    def test_run322_contains_exact_observed_two_stage_route(self):
        self.assertIn("run317.NEW_BODY_SHA256", RUN322)
        self.assertIn("run315.NEW_TITLE", RUN322)
        self.assertIn("run319.ARTICLE_LIST_URL", RUN322)
        self.assertIn('name=run321.EDIT_LABEL).click()', RUN322)
        self.assertIn('"公開されていない下書きがあります"', RUN322)
        self.assertIn('"公開した時点の記事"', RUN322)
        self.assertIn("run321.LATEST_DRAFT_LABEL", RUN322)
        self.assertIn('EDIT_CONFIRM_LABEL = "編集する"', RUN322)
        self.assertIn("_exact_visible_text(page, run321.LATEST_DRAFT_LABEL).click()", RUN322)
        self.assertIn('run321._visible_exact(page, role="button", name=EDIT_CONFIRM_LABEL).click()', RUN322)

    def test_run322_enters_publish_settings_but_never_final_commit(self):
        self.assertIn('run310._unique_button(page, "公開に進む").click()', RUN322)
        self.assertIn("run321._commit_candidates(rows)", RUN322)
        self.assertIn('"final_commit_clicked": False', RUN322)
        self.assertIn('"content_mutation": False', RUN322)
        self.assertIn('"settings_mutation": False', RUN322)
        self.assertIn('"membership_mutation": False', RUN322)
        self.assertIn('"public_mutation": False', RUN322)
        self.assertIn('"zero_gemini_calls": True', RUN322)
        self.assertIn('"notion_writes": 0', RUN322)
        self.assertNotIn('"更新する").click()', RUN322)
        self.assertNotIn('"公開する").click()', RUN322)

    def test_existing_hard_bound_workflow_and_chatops_advance_to_run323(self):
        token = "PROBE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_N284E428C80F4_SHAAAB9E57B"
        self.assertIn(token, WORKFLOW)
        self.assertIn("tests.test_run321b_member_onboarding_edit_route_diagnostic", WORKFLOW)
        self.assertIn("tests.test_run322_member_onboarding_version_confirm_publish_probe", WORKFLOW)
        self.assertIn("tests.test_run323_member_onboarding_publish_surface_deep_probe", WORKFLOW)
        self.assertIn("run323_member_onboarding_publish_surface_deep_probe.py", WORKFLOW)
        self.assertIn("/aiif note onboarding edit-route-probe", CHATOPS)
        self.assertIn("note-member-onboarding-official-edit-route-probe.yml", CHATOPS)
        self.assertIn(token, CHATOPS)
        upper = (WORKFLOW + CHATOPS).upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
