from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run314_member_onboarding_audit as run314

ROOT = Path(__file__).resolve().parents[1]


class Run314MemberOnboardingAuditTests(unittest.TestCase):
    def test_exact_target_is_hard_bound(self) -> None:
        self.assertEqual(run314.TARGET_NOTE_ID, "n284e428c80f4")
        self.assertEqual(run314.CONFIRM_TOKEN, "AUDIT_MEMBER_ONBOARDING_N284E428C80F4")
        self.assertEqual(run314.TARGET_PUBLIC_URL, "https://note.com/trendhub_biz/n/n284e428c80f4")

    def test_audit_reports_read_only_contract(self) -> None:
        source = inspect.getsource(run314.audit)
        self.assertIn('"public_mutation": False', source)
        self.assertIn('"read_only": True', source)
        self.assertIn('"zero_gemini_calls": True', source)

    def test_publish_stage_only_observes_settings(self) -> None:
        source = inspect.getsource(run314.audit)
        self.assertIn("_enter_publish_settings(page)", source)
        self.assertIn("_visible_form_controls(page)", source)
        self.assertIn("publish_settings_text", source)

    def test_workflow_is_manual_exact_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-member-onboarding-audit.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("AUDIT_MEMBER_ONBOARDING_N284E428C80F4", workflow)
        self.assertIn("run314_member_onboarding_audit.py", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)


if __name__ == "__main__":
    unittest.main()
