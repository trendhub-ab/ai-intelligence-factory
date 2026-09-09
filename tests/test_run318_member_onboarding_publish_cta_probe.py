from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run315_member_onboarding_update as run315
import run317_member_onboarding_server_save as run317
import run318_member_onboarding_publish_cta_probe as run318

ROOT = Path(__file__).resolve().parents[1]


class Run318MemberOnboardingPublishCtaProbeTests(unittest.TestCase):
    def test_probe_is_hard_bound_to_server_saved_revision(self) -> None:
        self.assertEqual(run318.CONFIRM_TOKEN, "PROBE_MEMBER_ONBOARDING_PUBLISH_CTA_N284E428C80F4_SHAAAB9E57B")
        source = inspect.getsource(run318.probe)
        self.assertIn("run315.NEW_TITLE", source)
        self.assertIn("run317.NEW_BODY_SHA256", source)
        self.assertIn("run315._verify_editor", source)
        self.assertIn("run315.TARGET_PUBLISH_URL", source)

    def test_probe_uses_clean_cookie_only_context(self) -> None:
        source = inspect.getsource(run318.probe)
        cookie_source = inspect.getsource(run318._cookie_source)
        self.assertIn("run317._launch_clean_browser", source)
        self.assertIn("run317._new_cookie_only_context", source)
        self.assertIn("cloud._launch_persistent_context", cookie_source)
        self.assertIn("run317._note_cookies", cookie_source)
        self.assertNotIn("_seed_note_state", cookie_source)
        self.assertNotIn("storage_state=", source)

    def test_probe_never_changes_membership_or_final_commit(self) -> None:
        source = inspect.getsource(run318.probe)
        self.assertNotIn("_ensure_membership_selected", source)
        self.assertNotIn("_membership_add_button", source)
        self.assertNotIn('_unique_button(page, "更新する")', source)
        self.assertNotIn('_unique_button(page, "公開する")', source)
        self.assertNotIn('_unique_button(page, "投稿する")', source)
        self.assertIn('"final_commit_clicked": False', source)
        self.assertIn('"membership_mutation": False', source)
        self.assertIn('"public_mutation": False', source)

    def test_candidate_inventory_covers_current_official_update_labels(self) -> None:
        source = inspect.getsource(run318._candidate_commit_controls)
        self.assertIn("更新する", source)
        self.assertIn("公開する", source)
        self.assertIn("投稿する", source)
        self.assertIn("保存する", source)

    def test_workflow_is_manual_exact_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-member-onboarding-publish-cta-probe.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("PROBE_MEMBER_ONBOARDING_PUBLISH_CTA_N284E428C80F4_SHAAAB9E57B", workflow)
        self.assertIn("run318_member_onboarding_publish_cta_probe.py", workflow)
        self.assertIn("final commit clicked: `false`", workflow)
        self.assertIn("membership mutation: `false`", workflow)
        self.assertIn("public mutation: `false`", workflow)
        self.assertIn("zero Gemini calls: `true`", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)

    def test_chatops_route_is_exact_and_probe_only(self) -> None:
        bridge = (ROOT / ".github" / "workflows" / "chatops-note.yml").read_text(encoding="utf-8")
        self.assertIn("/aiif note onboarding publish-probe", bridge)
        self.assertIn("onboarding_publish_probe", bridge)
        self.assertIn("note-member-onboarding-publish-cta-probe.yml", bridge)
        self.assertIn("publish-CTA inventory only", bridge)


if __name__ == "__main__":
    unittest.main()
