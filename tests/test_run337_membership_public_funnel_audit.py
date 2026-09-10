from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run311_note_profile_update as run311
import run332_membership_description_edit_route_probe as run332
import run333_membership_description_exact_update as run333
import run337_membership_public_funnel_audit as run337

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/note-membership-public-funnel-audit.yml").read_text(encoding="utf-8")


class Run337MembershipPublicFunnelAuditTests(unittest.TestCase):
    def test_exact_customer_surface_contract_is_pinned(self) -> None:
        self.assertEqual(run337.PUBLIC_MEMBERSHIP_URL, "https://note.com/trendhub_biz/membership")
        self.assertEqual(run333.MEMBERSHIP_NAME, "AI Decision Intelligence")
        self.assertEqual(len(run333.NEW_DESCRIPTION), 114)
        self.assertIn("最初にお読みください", run333.NEW_DESCRIPTION)
        self.assertIn("AI Decision Intelligenceの利用方法", run332.LEGACY_REFERENCE)
        self.assertIn("Product Hunt", run311.LEGACY_PROFILE)

    def test_price_parser_accepts_observed_public_variants_only(self) -> None:
        for value in ("¥1,980 / 月", "￥1,980/月", "1,980円/月"):
            self.assertTrue(run337._price_verified(value), value)
        self.assertFalse(run337._price_verified("980円/月"))
        self.assertFalse(run337._price_verified("月額 1,980円"))

    def test_join_candidate_detection_is_semantic_not_single_label(self) -> None:
        actions = [
            {"text": "メンバーシップに参加", "ariaLabel": "", "href": ""},
            {"text": "", "ariaLabel": "", "href": "https://note.com/membership/join?plan=x"},
            {"text": "詳細", "ariaLabel": "", "href": "https://note.com/help"},
        ]
        found = run337._join_candidates(actions)
        self.assertEqual(len(found), 2)

    def test_audit_is_fresh_logged_out_and_zero_mutation(self) -> None:
        source = inspect.getsource(run337.audit)
        self.assertIn("cookies_before = context.cookies()", source)
        self.assertIn("PUBLIC_MEMBERSHIP_URL", source)
        self.assertIn("run333.NEW_DESCRIPTION", source)
        self.assertIn("run332.LEGACY_REFERENCE", source)
        self.assertIn("run311.LEGACY_PROFILE", source)
        self.assertNotIn(".click(", source)
        self.assertNotIn(".fill(", source)
        self.assertNotIn("keyboard.type", source)
        self.assertIn('"clicks_performed": 0', source)
        self.assertIn('"field_filled": False', source)
        self.assertIn('"save_clicked": False', source)
        self.assertIn('"public_mutation": False', source)
        self.assertIn('"membership_mutation": False', source)
        self.assertIn('"zero_gemini_calls": True', source)
        self.assertIn('"notion_writes": 0', source)

    def test_workflow_is_manual_exact_zero_model(self) -> None:
        self.assertIn("/aiif note membership public-audit", WORKFLOW)
        self.assertIn(run337.CONFIRM_TOKEN, WORKFLOW)
        self.assertIn("run337_membership_public_funnel_audit.py", WORKFLOW)
        self.assertIn("tests.test_run337_membership_public_funnel_audit", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        upper = WORKFLOW.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
