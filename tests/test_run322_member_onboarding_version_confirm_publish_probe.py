from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run322_member_onboarding_version_confirm_publish_probe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-official-edit-route-probe.yml").read_text(encoding="utf-8")
CHATOPS = (ROOT / ".github/workflows/chatops-note.yml").read_text(encoding="utf-8")


class Run322VersionConfirmPublishProbeTests(unittest.TestCase):
    def test_exact_source_target_and_observed_two_stage_dialog(self):
        self.assertIn("run317.NEW_BODY_SHA256", SCRIPT)
        self.assertIn("run315.NEW_TITLE", SCRIPT)
        self.assertIn("run319.ARTICLE_LIST_URL", SCRIPT)
        self.assertIn('name=run321.EDIT_LABEL).click()', SCRIPT)
        self.assertIn('"公開されていない下書きがあります"', SCRIPT)
        self.assertIn('"どちらを編集しますか？"', SCRIPT)
        self.assertIn('"公開した時点の記事"', SCRIPT)
        self.assertIn("run321.LATEST_DRAFT_LABEL", SCRIPT)
        self.assertIn('EDIT_CONFIRM_LABEL = "編集する"', SCRIPT)

    def test_latest_is_selected_then_edit_confirm_is_clicked(self):
        latest_pos = SCRIPT.index("_exact_visible_text(page, run321.LATEST_DRAFT_LABEL).click()")
        confirm_pos = SCRIPT.index('run321._visible_exact(page, role="button", name=EDIT_CONFIRM_LABEL).click()')
        editor_verify_pos = SCRIPT.index("if not run315._is_exact_editor")
        self.assertLess(latest_pos, confirm_pos)
        self.assertLess(confirm_pos, editor_verify_pos)
        self.assertIn('"latest_draft_selected": True', SCRIPT)
        self.assertIn('"edit_confirm_clicked": True', SCRIPT)

    def test_reverifies_exact_revision_then_enters_publish_settings_only(self):
        self.assertIn("routed_title != run315.NEW_TITLE or routed_sha != run317.NEW_BODY_SHA256", SCRIPT)
        self.assertIn("run315._verify_editor(body)", SCRIPT)
        self.assertIn('run310._unique_button(page, "公開に進む").click()', SCRIPT)
        self.assertIn("run315.TARGET_PUBLISH_URL", SCRIPT)
        self.assertIn("run321._commit_candidates(rows)", SCRIPT)
        self.assertIn('"candidate_commit_controls": commit_candidates', SCRIPT)
        self.assertNotIn('"更新する").click()', SCRIPT)
        self.assertNotIn('"公開する").click()', SCRIPT)
        self.assertNotIn('"投稿する").click()', SCRIPT)

    def test_no_mutation_contract_and_existing_hard_bound_route(self):
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
        token = "PROBE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_N284E428C80F4_SHAAAB9E57B"
        self.assertIn("CONFIRM_TOKEN = run321.CONFIRM_TOKEN", SCRIPT)
        self.assertIn(token, WORKFLOW)
        self.assertIn("/aiif note onboarding edit-route-probe", CHATOPS)
        upper = (WORKFLOW + CHATOPS).upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
