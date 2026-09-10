from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run311_note_profile_update as run311
import run333_membership_description_exact_update as run333
import run337_membership_public_funnel_audit as run337
import run338_membership_public_surface_diagnostic as run338

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/note-membership-public-surface-diagnostic.yml").read_text(encoding="utf-8")


class Run338MembershipPublicSurfaceDiagnosticTests(unittest.TestCase):
    def test_exact_public_targets_and_checkpoints_are_pinned(self) -> None:
        self.assertEqual(run338.PUBLIC_MEMBERSHIP_URL, "https://note.com/trendhub_biz/membership")
        self.assertEqual(run338.PUBLIC_PROFILE_URL, run311.PUBLIC_PROFILE_URL)
        self.assertEqual(run338.CHECKPOINT_DELAYS_MS, (0, 1500, 2500, 4000))
        self.assertEqual(run333.MEMBERSHIP_NAME, "AI Decision Intelligence")
        self.assertEqual(len(run333.NEW_DESCRIPTION), 114)

    def test_classification_distinguishes_rendering_and_missing_surface(self) -> None:
        good = [{
            "markers": {
                "membership_name_in_body": True,
                "membership_name_in_html": True,
                "current_description_in_body": True,
                "price_in_body": True,
                "challenge_hits": [],
                "not_available_hits": [],
            },
            "join_candidates": [{"text": "参加"}],
        }]
        self.assertEqual(run338._classify(good, []), "public_purchase_surface_current")

        hidden = [{
            "markers": {
                "membership_name_in_body": False,
                "membership_name_in_html": True,
                "challenge_hits": [],
                "not_available_hits": [],
            },
            "join_candidates": [],
        }]
        self.assertEqual(run338._classify(hidden, []), "membership_data_present_but_not_visible")

        missing = [{
            "markers": {
                "membership_name_in_body": False,
                "membership_name_in_html": False,
                "challenge_hits": [],
                "not_available_hits": [],
            },
            "join_candidates": [],
        }]
        self.assertEqual(
            run338._classify(missing, [{"href": "/trendhub_biz/membership", "text": "メンバーシップ"}]),
            "profile_links_membership_but_target_surface_missing_expected_content",
        )

    def test_diagnostic_collects_evidence_without_customer_mutation(self) -> None:
        source = inspect.getsource(run338.diagnose)
        self.assertIn("membership_checkpoints", source)
        self.assertIn("request_failures", source)
        self.assertIn("http_error_responses", source)
        self.assertIn("console_errors", source)
        self.assertIn("page_errors", source)
        self.assertIn("PUBLIC_MEMBERSHIP_URL", source)
        self.assertIn("PUBLIC_PROFILE_URL", source)
        self.assertIn("profile_membership_links", source)
        self.assertIn("page.wait_for_load_state(\"networkidle\"", source)
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

    def test_main_persists_runtime_error_instead_of_losing_evidence(self) -> None:
        source = inspect.getsource(run338.main)
        self.assertIn("diagnostic_runtime_error_no_mutation", source)
        self.assertIn("write_text", source)
        self.assertIn("RUN338_MEMBERSHIP_PUBLIC_SURFACE_DIAGNOSTIC", source)

    def test_workflow_is_manual_exact_read_only_and_preserves_all_evidence(self) -> None:
        self.assertIn("/aiif note membership public-diagnostic", WORKFLOW)
        self.assertIn(run338.CONFIRM_TOKEN, WORKFLOW)
        self.assertIn("run338_membership_public_surface_diagnostic.py", WORKFLOW)
        self.assertIn("tests.test_run338_membership_public_surface_diagnostic", WORKFLOW)
        self.assertIn("run338-membership-public-diagnostic.json", WORKFLOW)
        self.assertIn("run338-membership-public.png", WORKFLOW)
        self.assertIn("run338-profile-public.png", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        upper = WORKFLOW.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
