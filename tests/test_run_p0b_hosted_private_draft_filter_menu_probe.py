from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run_p0b_hosted_private_draft_filter_menu_probe as probe

ROOT = Path(__file__).resolve().parents[1]


class P0BHostedPrivateDraftFilterMenuProbeTests(unittest.TestCase):
    def test_status_control_wait_is_bounded_visible_exact_and_read_only(self) -> None:
        source = inspect.getsource(probe._wait_for_unique_visible_exact_text)
        self.assertIn("get_by_text", source)
        self.assertIn("exact=True", source)
        self.assertIn("attempts=32", source)
        self.assertIn("interval_ms=250", source)
        self.assertIn("is_visible", source)
        self.assertIn("len(visible_indices) > 1", source)
        self.assertNotIn(".click(", source)

    def test_status_menu_open_uses_unique_visible_wait_and_single_click(self) -> None:
        source = inspect.getsource(probe._open_status_filter_menu)
        self.assertIn('_wait_for_unique_visible_exact_text(page, "公開ステータス")', source)
        self.assertEqual(source.count(".click("), 1)

    def test_actionable_draft_candidates_are_role_bounded_and_read_only(self) -> None:
        self.assertEqual(
            probe.ACTIONABLE_ROLES,
            ("button", "link", "menuitem", "menuitemradio", "option", "radio"),
        )
        source = inspect.getsource(probe._visible_exact_actionable_role_counts)
        self.assertIn("get_by_role", source)
        self.assertIn("exact=True", source)
        self.assertNotIn(".click(", source)

    def test_probe_only_observes_draft_option_after_opening_status_menu(self) -> None:
        source = inspect.getsource(probe.probe)
        self.assertIn("ARTICLE_LIST_URL", source)
        self.assertIn("_open_status_filter_menu", source)
        self.assertIn("_visible_exact_text_count", source)
        self.assertIn("_visible_exact_actionable_role_counts", source)
        self.assertIn('"下書き"', source)
        self.assertIn("_looks_logged_out", source)
        for forbidden in (".fill(", ".type(", ".press(", "editor.note.com/new"):
            self.assertNotIn(forbidden, source)

    def test_result_schema_is_safe_aggregate_only(self) -> None:
        self.assertEqual(
            probe.SAFE_RESULT_KEYS,
            {
                "status",
                "authenticated",
                "status_filter_control_count",
                "draft_filter_option_count",
                "draft_actionable_role_counts",
                "final_route_shape",
                "zero_model_calls",
                "mutation_count",
            },
        )

    def test_workflow_is_hosted_only_and_recovery_branch_bounded(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "p0b-hosted-private-draft-filter-menu-probe.yml").read_text(encoding="utf-8")
        self.assertIn("ops/p0b-hosted-b01-recovery-20261006", workflow)
        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertIn("NOTE_STORAGE_STATE_B64", workflow)
        self.assertIn("run_p0b_hosted_private_draft_filter_menu_probe.py", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("GCP_NOTE_VM", workflow)
        self.assertNotIn("NOTION_TOKEN", workflow)
        self.assertNotIn("GEMINI", workflow)
        self.assertNotIn("actions: write", workflow)


if __name__ == "__main__":
    unittest.main()
