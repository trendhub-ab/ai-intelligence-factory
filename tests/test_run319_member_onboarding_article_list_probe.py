from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run315_member_onboarding_update as run315
import run317_member_onboarding_server_save as run317
import run319_member_onboarding_article_list_probe as run319

ROOT = Path(__file__).resolve().parents[1]


class Run319MemberOnboardingArticleListProbeTests(unittest.TestCase):
    def test_probe_is_exact_and_server_saved_source_only(self) -> None:
        self.assertEqual(run319.CONFIRM_TOKEN, "PROBE_MEMBER_ONBOARDING_ARTICLE_LIST_N284E428C80F4_SHAAAB9E57B")
        self.assertEqual(run319.ARTICLE_LIST_URL, "https://note.com/notes")
        self.assertIn(run315.TARGET_NOTE_ID, run319.TARGET_PUBLIC_PATH)
        source = inspect.getsource(run319.probe)
        self.assertIn("run315.NEW_TITLE", source)
        self.assertIn("run317.NEW_BODY_SHA256", source)
        self.assertIn("run315._verify_editor", source)

    def test_probe_uses_clean_cookie_only_browser(self) -> None:
        source = inspect.getsource(run319.probe)
        self.assertIn("run318._cookie_source", source)
        self.assertIn("run317._launch_clean_browser", source)
        self.assertIn("run317._new_cookie_only_context", source)
        self.assertNotIn("storage_state=", source)

    def test_only_target_card_menu_may_be_opened(self) -> None:
        mark = inspect.getsource(run319._mark_target_card)
        opener = inspect.getsource(run319._open_menu_if_exact)
        self.assertIn("TARGET_PUBLIC_PATH", mark)
        self.assertIn("data-run319-target-card", mark)
        self.assertIn("len(indices) != 1", opener)
        self.assertIn("candidate.click()", opener)

    def test_membership_action_is_observed_but_never_clicked(self) -> None:
        source = inspect.getsource(run319.probe)
        matches = inspect.getsource(run319._membership_menu_matches)
        self.assertIn("メンバーシップ特典に追加", matches)
        self.assertIn("メンバーシップに追加", matches)
        self.assertNotIn("membership_matches[0].click", source)
        self.assertIn('"menu_action_clicked": False', source)
        self.assertIn('"membership_mutation": False', source)
        self.assertIn('"public_mutation": False', source)

    def test_workflow_is_manual_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-member-onboarding-article-list-probe.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("PROBE_MEMBER_ONBOARDING_ARTICLE_LIST_N284E428C80F4_SHAAAB9E57B", workflow)
        self.assertIn("run319_member_onboarding_article_list_probe.py", workflow)
        self.assertIn("menu action clicked: `false`", workflow)
        self.assertIn("membership mutation: `false`", workflow)
        self.assertIn("public mutation: `false`", workflow)
        self.assertIn("zero Gemini calls: `true`", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)

    def test_chatops_route_is_exact_probe_only(self) -> None:
        bridge = (ROOT / ".github" / "workflows" / "chatops-note.yml").read_text(encoding="utf-8")
        self.assertIn("/aiif note onboarding list-probe", bridge)
        self.assertIn("onboarding_list_probe", bridge)
        self.assertIn("note-member-onboarding-article-list-probe.yml", bridge)
        self.assertIn("article-list membership-route inventory only", bridge)


if __name__ == "__main__":
    unittest.main()
