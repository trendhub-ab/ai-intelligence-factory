from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run_p0b_hosted_private_draft_filter_navigation_probe as probe

ROOT = Path(__file__).resolve().parents[1]


class P0BHostedPrivateDraftFilterNavigationProbeTests(unittest.TestCase):
    def test_draft_selection_requires_the_proven_unique_menuitemradio_shape(self) -> None:
        source = inspect.getsource(probe._select_unique_draft_filter)
        self.assertIn("_visible_exact_actionable_role_counts", source)
        self.assertIn('"menuitemradio": 1', source)
        self.assertIn('get_by_role("menuitemradio", name="下書き", exact=True)', source)
        self.assertIn("count()", source)
        self.assertIn("!= 1", source)
        self.assertEqual(source.count(".click("), 1)

    def test_probe_has_exact_two_navigation_clicks_and_no_content_editing(self) -> None:
        source = inspect.getsource(probe.probe)
        self.assertIn("_open_status_filter_menu", source)
        self.assertIn("_select_unique_draft_filter", source)
        self.assertIn("_visible_route_shapes", source)
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
                "draft_filter_selected",
                "draft_filter_role",
                "final_route_shape",
                "visible_anchor_count",
                "anchor_route_shape_counts",
                "draft_marker_count",
                "published_marker_count",
                "ui_navigation_click_count",
                "zero_model_calls",
                "mutation_count",
            },
        )

    def test_workflow_is_hosted_only_branch_bounded_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "p0b-hosted-private-draft-filter-navigation-probe.yml").read_text(encoding="utf-8")
        self.assertIn("ops/p0b-hosted-b01-recovery-20261006", workflow)
        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertIn("NOTE_STORAGE_STATE_B64", workflow)
        self.assertIn("run_p0b_hosted_private_draft_filter_navigation_probe.py", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("GCP_NOTE_VM", workflow)
        self.assertNotIn("NOTION_TOKEN", workflow)
        self.assertNotIn("GEMINI", workflow)
        self.assertNotIn("actions: write", workflow)


if __name__ == "__main__":
    unittest.main()
