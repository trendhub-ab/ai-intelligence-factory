from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run324_member_onboarding_trial_read_surface_probe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-trial-read-surface-probe.yml").read_text(encoding="utf-8")
CHATOPS = (ROOT / ".github/workflows/chatops-note.yml").read_text(encoding="utf-8")


class Run324TrialReadSurfaceProbeTests(unittest.TestCase):
    def test_exact_source_and_proven_existing_article_route(self):
        self.assertIn("run317.NEW_BODY_SHA256", SCRIPT)
        self.assertIn("run315.NEW_TITLE", SCRIPT)
        self.assertIn("run319.ARTICLE_LIST_URL", SCRIPT)
        self.assertIn('name=run321.EDIT_LABEL).click()', SCRIPT)
        self.assertIn("run322._select_latest_and_confirm(page)", SCRIPT)
        self.assertIn('run310._unique_button(page, "公開に進む").click()', SCRIPT)
        self.assertIn("run315.TARGET_PUBLISH_URL", SCRIPT)

    def test_run323_missing_update_is_required_before_trial_read_click(self):
        self.assertIn('FINAL_UPDATE_LABEL = "更新する"', SCRIPT)
        self.assertIn('TRIAL_READ_LABEL = "試し読みエリアを設定"', SCRIPT)
        self.assertIn("pre_update_count != 0", SCRIPT)
        self.assertIn("pre_trial_count != 1", SCRIPT)
        self.assertIn("publish_settings_before_trial_read", SCRIPT)

    def test_only_trial_read_intermediate_cta_is_clicked(self):
        self.assertIn("run310._unique_button(page, TRIAL_READ_LABEL).click()", SCRIPT)
        self.assertIn('"trial_read_cta_clicked": True', SCRIPT)
        self.assertIn('"trial_read_line_clicked": False', SCRIPT)
        self.assertNotIn('LINE_LABEL_FRAGMENT).click()', SCRIPT)
        self.assertNotIn('FINAL_UPDATE_LABEL).click()', SCRIPT)
        self.assertNotIn('"更新する").click()', SCRIPT)
        self.assertNotIn('"公開する").click()', SCRIPT)
        self.assertNotIn('"投稿する").click()', SCRIPT)
        self.assertNotIn('"保存する").click()', SCRIPT)

    def test_post_trial_surface_is_forensically_inventoried(self):
        for marker in ("trial_read_after_t1", "trial_read_after_t3", "trial_read_bottom"):
            self.assertIn(marker, SCRIPT)
        self.assertIn("post_exact_update_count", SCRIPT)
        self.assertIn("trial_read_line_candidate_count", SCRIPT)
        self.assertIn("url_after_trial_read", SCRIPT)
        self.assertIn("run323._deep_surface", SCRIPT)
        self.assertIn("run323._candidate_labels", SCRIPT)
        self.assertIn("page.screenshot", SCRIPT)

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

    def test_workflow_and_chatops_are_hard_bound_and_zero_model(self):
        token = "PROBE_MEMBER_ONBOARDING_TRIAL_READ_SURFACE_N284E428C80F4_SHAAAB9E57B"
        self.assertIn(token, SCRIPT)
        self.assertIn(token, WORKFLOW)
        self.assertIn("run324_member_onboarding_trial_read_surface_probe.py", WORKFLOW)
        self.assertIn("tests.test_run324_member_onboarding_trial_read_surface_probe", WORKFLOW)
        self.assertIn("run324-result.json", WORKFLOW)
        self.assertIn("run324-trial-read-surface.png", WORKFLOW)
        self.assertIn("/aiif note onboarding trial-read-probe", CHATOPS)
        self.assertIn("note-member-onboarding-trial-read-surface-probe.yml", CHATOPS)
        upper = (WORKFLOW + CHATOPS).upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
