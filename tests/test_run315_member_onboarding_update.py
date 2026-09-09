from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run315_member_onboarding_update as run315

ROOT = Path(__file__).resolve().parents[1]


class Run315MemberOnboardingUpdateTests(unittest.TestCase):
    def test_exact_audited_target_is_hard_bound(self) -> None:
        self.assertEqual(run315.TARGET_NOTE_ID, "n284e428c80f4")
        self.assertEqual(run315.AUDITED_BODY_SHA256, "4826aabc101f5f5319e2ea441e0e929ce2e7ee382be10a5fd0a976583c49c9f4")
        self.assertEqual(run315.CONFIRM_TOKEN, "UPDATE_MEMBER_ONBOARDING_N284E428C80F4_SHA4826AABC")

    def test_current_onboarding_copy_is_generic_and_actionable(self) -> None:
        self.assertIn("「このAI、使える！」を判断するための使い方", run315.NEW_TITLE)
        for marker in run315.REQUIRED_MARKERS:
            self.assertIn(marker, run315.MANUSCRIPT)
        for marker in run315.FORBIDDEN_OLD_MARKERS:
            self.assertNotIn(marker, run315.MANUSCRIPT)
        self.assertIn("自分の開発", run315.MANUSCRIPT)
        self.assertIn("業務利用", run315.MANUSCRIPT)
        self.assertIn("必要に応じた提案", run315.MANUSCRIPT)

    def test_real_member_destinations_are_embedded(self) -> None:
        for url in (run315.FORM_URL, run315.BRIEF_URL, run315.DB_URL, run315.MEMO_URL):
            self.assertIn(url, run315.MANUSCRIPT)
        self.assertTrue(run315.DB_URL.startswith("https://app.notion.com/"))

    def test_updater_requires_exact_sha_or_authorized_staged_copy(self) -> None:
        source = inspect.getsource(run315.update)
        self.assertIn("_sha256(current_body) != AUDITED_BODY_SHA256", source)
        self.assertIn("current_title == NEW_TITLE", source)
        self.assertIn("_verify_editor(body)", source)
        self.assertIn("refuses onboarding body drift", source)

    def test_membership_reassociation_is_explicit_and_fail_closed(self) -> None:
        source = inspect.getsource(run315._ensure_membership_selected)
        self.assertIn("_membership_add_button(page)", source)
        self.assertIn("_choose_all_members_if_prompted(page)", source)
        self.assertIn("membership association did not leave the audited Add state", source)
        self.assertEqual(run315.MEMBERSHIP_NAME, "AI Intelligence Factory")

    def test_public_verification_rejects_not_for_sale(self) -> None:
        source = inspect.getsource(run315._verify_public)
        self.assertIn("この記事は現在販売されていません", source)
        self.assertIn("NEW_TITLE", source)
        self.assertIn('"not_for_sale_removed": True', source)

    def test_workflow_is_manual_exact_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-member-onboarding-update.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("UPDATE_MEMBER_ONBOARDING_N284E428C80F4_SHA4826AABC", workflow)
        self.assertIn("run315_member_onboarding_update.py", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("zero Gemini calls", workflow)


if __name__ == "__main__":
    unittest.main()
