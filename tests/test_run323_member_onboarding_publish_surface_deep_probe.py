from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run323_member_onboarding_publish_surface_deep_probe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-official-edit-route-probe.yml").read_text(encoding="utf-8")
CHATOPS = (ROOT / ".github/workflows/chatops-note.yml").read_text(encoding="utf-8")


class Run323PublishSurfaceDeepProbeTests(unittest.TestCase):
    def test_exact_source_and_proven_run322_route(self):
        self.assertIn("run317.NEW_BODY_SHA256", SCRIPT)
        self.assertIn("run315.NEW_TITLE", SCRIPT)
        self.assertIn("run319.ARTICLE_LIST_URL", SCRIPT)
        self.assertIn('name=run321.EDIT_LABEL).click()', SCRIPT)
        self.assertIn("run322._select_latest_and_confirm(page)", SCRIPT)
        self.assertIn('run310._unique_button(page, "公開に進む").click()', SCRIPT)
        self.assertIn("run315.TARGET_PUBLISH_URL", SCRIPT)

    def test_deep_probe_covers_hidden_disabled_forms_and_fixed_layers(self):
        self.assertIn("hiddenOrDisabledBroad", SCRIPT)
        self.assertIn("document.forms", SCRIPT)
        self.assertIn("fixedSticky", SCRIPT)
        self.assertIn("'[onclick]'", SCRIPT)
        self.assertIn("'[tabindex]'", SCRIPT)
        self.assertIn("'[role]'", SCRIPT)
        self.assertIn("keywordMatches", SCRIPT)
        self.assertIn("outerHTML", SCRIPT)
        self.assertIn("page.set_viewport_size", SCRIPT)
        for label in ("top_t1s", "top_t3s", "bottom_t4s", "bottom_t8s", "top_final"):
            self.assertIn(label, SCRIPT)

    def test_forensic_screenshot_and_result_are_preserved(self):
        self.assertIn("page.screenshot", SCRIPT)
        self.assertIn("actions/upload-artifact@v4", WORKFLOW)
        self.assertIn("run323-result.json", WORKFLOW)
        self.assertIn("run323-publish-surface.png", WORKFLOW)

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
        self.assertNotIn('"更新する").click()', SCRIPT)
        self.assertNotIn('"公開する").click()', SCRIPT)
        self.assertNotIn('"投稿する").click()', SCRIPT)
        self.assertNotIn('"保存する").click()', SCRIPT)

    def test_existing_hard_bound_route_is_reused(self):
        token = "PROBE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_N284E428C80F4_SHAAAB9E57B"
        self.assertIn("CONFIRM_TOKEN = run321.CONFIRM_TOKEN", SCRIPT)
        self.assertIn(token, WORKFLOW)
        self.assertIn("run323_member_onboarding_publish_surface_deep_probe.py", WORKFLOW)
        self.assertIn("tests.test_run323_member_onboarding_publish_surface_deep_probe", WORKFLOW)
        self.assertIn("/aiif note onboarding edit-route-probe", CHATOPS)
        self.assertIn("note-member-onboarding-official-edit-route-probe.yml", CHATOPS)
        upper = (WORKFLOW + CHATOPS).upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
