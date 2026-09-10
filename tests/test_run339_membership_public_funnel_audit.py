from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run311_note_profile_update as run311
import run315_member_onboarding_update as run315
import run332_membership_description_edit_route_probe as run332
import run333_membership_description_exact_update as run333
import run339_membership_public_funnel_audit as run339

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/note-membership-public-funnel-audit.yml").read_text(encoding="utf-8")


class Run339MembershipPublicFunnelAuditTests(unittest.TestCase):
    def test_exact_observed_route_and_customer_contract_are_pinned(self) -> None:
        self.assertEqual(run339.PUBLIC_MEMBERSHIP_URL, "https://note.com/trendhub_biz/membership")
        self.assertEqual(run339.PUBLIC_MEMBERSHIP_JOIN_URL, "https://note.com/trendhub_biz/membership/join")
        self.assertEqual(run339.HYDRATION_TIMEOUT_MS, 12000)
        self.assertEqual(run339.HYDRATION_POLL_MS, 250)
        self.assertEqual(run333.MEMBERSHIP_NAME, "AI Decision Intelligence")
        self.assertEqual(len(run333.NEW_DESCRIPTION), 114)
        self.assertIn("AI Decision Intelligenceの利用方法", run332.LEGACY_REFERENCE)
        self.assertIn("Product Hunt", run311.LEGACY_PROFILE)
        self.assertEqual(run315.TARGET_PUBLIC_URL, "https://note.com/trendhub_biz/n/n284e428c80f4")

    def test_logged_out_ui_requires_both_login_and_registration(self) -> None:
        self.assertTrue(run339._logged_out_ui_verified([
            {"text": "ログイン", "ariaLabel": "", "href": "/login"},
            {"text": "会員登録", "ariaLabel": "", "href": ""},
        ]))
        self.assertFalse(run339._logged_out_ui_verified([{"text": "ログイン", "ariaLabel": "", "href": "/login"}]))

    def test_note_gql_auth_token_is_anonymous_only_with_positive_logged_out_ui(self) -> None:
        observed = ["_note_session_v5", "note_gql_auth_token", "note_web_visitor_id"]
        self.assertEqual(run339._explicit_auth_cookie_names(observed, True), [])
        self.assertEqual(run339._explicit_auth_cookie_names(observed, False), ["note_gql_auth_token"])

    def test_unknown_auth_like_cookie_remains_fail_closed(self) -> None:
        observed = ["note_gql_auth_token", "future_login_token", "mystery_auth"]
        self.assertEqual(
            run339._explicit_auth_cookie_names(observed, True),
            ["future_login_token", "mystery_auth"],
        )

    def test_hydrated_state_requires_plan_description_price_join_and_logged_out_ui(self) -> None:
        body = f"{run333.MEMBERSHIP_NAME} {run333.NEW_DESCRIPTION} ¥1,980 / 月 参加手続きへ"
        actions = [
            {"text": "ログイン", "ariaLabel": "", "href": "/login"},
            {"text": "会員登録", "ariaLabel": "", "href": ""},
            {"text": "参加手続きへ", "ariaLabel": "", "href": ""},
        ]
        self.assertTrue(run339._hydrated_customer_state(body, actions))
        self.assertFalse(run339._hydrated_customer_state(body, actions[:2]))

    def test_audit_waits_for_hydration_and_is_zero_mutation(self) -> None:
        source = inspect.getsource(run339.audit)
        wait_source = inspect.getsource(run339._wait_for_hydrated_purchase_surface)
        self.assertIn("_wait_for_hydrated_purchase_surface(page)", source)
        self.assertIn("PUBLIC_MEMBERSHIP_JOIN_URL", source)
        self.assertIn("_explicit_auth_cookie_names", source)
        self.assertIn("logged_out_ui_verified", source)
        self.assertIn("benefits_verified", source)
        self.assertIn("onboarding_link_verified", source)
        self.assertIn("page.wait_for_timeout(HYDRATION_POLL_MS)", wait_source)
        self.assertNotIn(".click(", source)
        self.assertNotIn(".fill(", source)
        self.assertNotIn("keyboard.type", source)
        self.assertNotIn("keyboard.press", source)
        self.assertIn('"clicks_performed": 0', source)
        self.assertIn('"field_filled": False', source)
        self.assertIn('"save_clicked": False', source)
        self.assertIn('"membership_mutation": False', source)
        self.assertIn('"public_mutation": False', source)
        self.assertIn('"zero_gemini_calls": True', source)
        self.assertIn('"notion_writes": 0', source)

    def test_workflow_promotes_live_command_to_run339(self) -> None:
        self.assertIn("/aiif note membership public-audit", WORKFLOW)
        self.assertIn(run339.CONFIRM_TOKEN, WORKFLOW)
        self.assertIn("run339_membership_public_funnel_audit.py", WORKFLOW)
        self.assertIn("tests.test_run339_membership_public_funnel_audit", WORKFLOW)
        self.assertNotIn("NOTE_MEMBERSHIP_PUBLIC_RUN337_CONFIRM", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        upper = WORKFLOW.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
