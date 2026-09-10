from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run332_membership_description_edit_route_probe as run332

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "note-member-onboarding-membership-dialog-probe.yml").read_text(encoding="utf-8")


class Run332MembershipDescriptionEditRouteProbeTests(unittest.TestCase):
    def test_exact_business_surface_and_stale_reference_are_pinned(self) -> None:
        self.assertEqual(run332.PUBLIC_PROFILE_URL, "https://note.com/trendhub_biz")
        self.assertEqual(run332.MEMBERSHIP_NAME, "AI Decision Intelligence")
        self.assertIn("AI Decision Intelligenceの利用方法", run332.LEGACY_REFERENCE)
        self.assertIn("このAI、使える！", run332.CURRENT_ONBOARDING_TITLE)

    def test_public_edit_href_is_audited_then_directly_navigated_without_click(self) -> None:
        source = inspect.getsource(run332.probe)
        finder = inspect.getsource(run332._find_membership_edit_link)
        self.assertIn("_find_membership_edit_link(page)", source)
        self.assertIn("page.goto(href", source)
        self.assertIn("new URL", finder)
        self.assertIn("note.com", finder)
        self.assertNotIn(".click()", source)
        self.assertNotIn(".click()", finder)

    def test_probe_has_zero_fill_zero_save_zero_mutation_contract(self) -> None:
        source = inspect.getsource(run332.probe)
        self.assertNotIn(".fill(", source)
        self.assertNotIn("insert_text", source)
        self.assertNotIn("keyboard.type", source)
        self.assertIn('"clicks_performed": 0', source)
        self.assertIn('"field_filled": False', source)
        self.assertIn('"save_clicked": False', source)
        self.assertIn('"membership_mutation": False', source)
        self.assertIn('"public_mutation": False', source)
        self.assertIn('"zero_gemini_calls": True', source)
        self.assertIn('"notion_writes": 0', source)

    def test_probe_inventories_description_limits_and_save_controls(self) -> None:
        inventory = inspect.getsource(run332._surface_inventory)
        self.assertIn("maxLength", inventory)
        self.assertIn("valueExcerpt", inventory)
        self.assertIn("placeholder", inventory)
        self.assertIn("ariaLabel", inventory)
        self.assertIn("button", inventory)
        self.assertIn("a[href]", inventory)
        self.assertIn("_description_candidates", inspect.getsource(run332.probe))
        self.assertIn("_save_candidates", inspect.getsource(run332.probe))

    def test_run332_is_preserved_as_history_while_live_workflow_advances(self) -> None:
        self.assertNotIn("/aiif note membership description-probe", WORKFLOW)
        self.assertNotIn("run332_membership_description_edit_route_probe.py", WORKFLOW)
        self.assertIn("/aiif note membership description-update", WORKFLOW)
        self.assertIn("run333_membership_description_exact_update.py", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        upper = WORKFLOW.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
