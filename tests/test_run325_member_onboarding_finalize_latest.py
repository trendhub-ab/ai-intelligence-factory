from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run325_member_onboarding_finalize_latest.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-member-onboarding-finalize-latest.yml").read_text(encoding="utf-8")
CHATOPS = (ROOT / ".github/workflows/chatops-note.yml").read_text(encoding="utf-8")


class Run325MemberOnboardingFinalizeLatestTests(unittest.TestCase):
    def test_exact_target_latest_sha_and_existing_article_route(self):
        self.assertIn("run317.NEW_BODY_SHA256", SCRIPT)
        self.assertIn("run315.NEW_TITLE", SCRIPT)
        self.assertIn("run315.AUDITED_TITLE", SCRIPT)
        self.assertIn("run319.ARTICLE_LIST_URL", SCRIPT)
        self.assertIn('name=run321.EDIT_LABEL).click()', SCRIPT)
        self.assertIn("run322._select_latest_and_confirm(page)", SCRIPT)
        self.assertIn('run310._unique_button(page, "公開に進む").click()', SCRIPT)

    def test_trial_read_bridge_is_required_and_line_is_never_selected(self):
        self.assertIn('TRIAL_READ_LABEL = "試し読みエリアを設定"', SCRIPT)
        self.assertIn('FINAL_UPDATE_LABEL = "更新する"', SCRIPT)
        self.assertIn("run310._unique_button(page, TRIAL_READ_LABEL).click()", SCRIPT)
        self.assertIn("run324._line_candidate_count(page)", SCRIPT)
        self.assertIn('"trial_read_line_clicked": False', SCRIPT)
        self.assertNotIn('LINE_LABEL_FRAGMENT).click()', SCRIPT)
        self.assertNotIn('"ラインをこの場所に変更").click()', SCRIPT)

    def test_final_update_is_exactly_one_explicit_mutation(self):
        self.assertIn("_visible_exact_button_count(page, FINAL_UPDATE_LABEL) != 1", SCRIPT)
        self.assertEqual(SCRIPT.count("run310._unique_button(page, FINAL_UPDATE_LABEL).click()"), 1)
        self.assertIn('"final_update_clicked": True', SCRIPT)
        self.assertIn('"public_mutation": True', SCRIPT)
        self.assertNotIn('"公開する").click()', SCRIPT)
        self.assertNotIn('"投稿する").click()', SCRIPT)
        self.assertNotIn('"保存する").click()', SCRIPT)

    def test_idempotency_and_public_card_convergence_are_fail_closed(self):
        self.assertIn("already_current_verified_no_mutation", SCRIPT)
        self.assertIn('UNPUBLISHED_DRAFT_MARKER = "追加編集された未公開の下書きがあります"', SCRIPT)
        self.assertIn("Run325 refuses ambiguous pre-update card", SCRIPT)
        self.assertIn("Run325 post-update card does not show new title", SCRIPT)
        self.assertIn("Run325 post-update card still reports an unpublished draft", SCRIPT)
        self.assertIn('"公開中"', SCRIPT)

    def test_membership_postcondition_preserves_specific_plan_and_not_all_plans(self):
        self.assertIn('PLAN_NAME = "AI Decision Intelligence"', SCRIPT)
        self.assertIn('ALL_PLANS_NOT_ADDED_MARKER = "すべてのプラン（全員に公開） 追加"', SCRIPT)
        self.assertIn("run320._membership_surface(page)", SCRIPT)
        self.assertIn('"membership_mutation": False', SCRIPT)
        self.assertIn('"members_only_access_preserved": True', SCRIPT)
        self.assertIn('"all_plans_exposure_preserved_false": True', SCRIPT)

    def test_zero_model_zero_notion_and_hard_bound_workflow(self):
        token = "FINALIZE_MEMBER_ONBOARDING_N284E428C80F4_SHAAAB9E57B_KEEP_MEMBERS_ONLY"
        self.assertIn(token, SCRIPT)
        self.assertIn(token, WORKFLOW)
        self.assertIn("run325_member_onboarding_finalize_latest.py", WORKFLOW)
        self.assertIn("tests.test_run325_member_onboarding_finalize_latest", WORKFLOW)
        self.assertIn("run325-result.json", WORKFLOW)
        self.assertIn("/aiif note onboarding finalize-latest", CHATOPS)
        self.assertIn("note-member-onboarding-finalize-latest.yml", CHATOPS)
        upper = (WORKFLOW + CHATOPS).upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
