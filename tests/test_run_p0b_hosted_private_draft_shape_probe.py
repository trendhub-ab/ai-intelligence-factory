from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run_p0b_hosted_private_draft_shape_probe as probe

ROOT = Path(__file__).resolve().parents[1]


class P0BHostedPrivateDraftShapeProbeTests(unittest.TestCase):
    def test_route_shape_redacts_private_segments_and_queries(self) -> None:
        self.assertEqual(probe._safe_route_shape("https://note.com/notes"), "note.com/notes")
        self.assertEqual(
            probe._safe_route_shape("https://note.com/private_account/n/n0123456789abcdef?foo=secret"),
            "note.com/{segment}/n/{segment}",
        )
        shaped = probe._safe_route_shape("https://editor.note.com/notes/private-draft-id/edit?token=secret")
        self.assertEqual(shaped, "editor.note.com/notes/{segment}/edit")
        self.assertNotIn("private-draft-id", shaped)
        self.assertNotIn("secret", shaped)

    def test_external_hosts_are_not_exposed(self) -> None:
        self.assertEqual(
            probe._safe_route_shape("https://example.com/private/account/path?token=secret"),
            "{external}",
        )

    def test_probe_is_strictly_read_only(self) -> None:
        source = inspect.getsource(probe.probe)
        self.assertIn("ARTICLE_LIST_URL", source)
        self.assertIn("_looks_logged_out", source)
        for forbidden in (".click(", ".fill(", ".type(", ".press(", "editor.note.com/new"):
            self.assertNotIn(forbidden, source)

    def test_probe_returns_only_aggregate_safe_fields(self) -> None:
        self.assertEqual(
            probe.SAFE_RESULT_KEYS,
            {
                "status",
                "authenticated",
                "final_route_shape",
                "anchor_route_shape_counts",
                "draft_marker_count",
                "published_marker_count",
                "visible_anchor_count",
                "zero_model_calls",
                "mutation_count",
            },
        )

    def test_workflow_is_hosted_only_and_branch_bounded(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "p0b-hosted-private-draft-shape-probe.yml").read_text(encoding="utf-8")
        self.assertIn("ops/p0b-hosted-b01-recovery-20261006", workflow)
        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertIn("NOTE_STORAGE_STATE_B64", workflow)
        self.assertIn("run_p0b_hosted_private_draft_shape_probe.py", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("GCP_NOTE_VM", workflow)
        self.assertNotIn("NOTION_TOKEN", workflow)
        self.assertNotIn("GEMINI", workflow)


if __name__ == "__main__":
    unittest.main()
