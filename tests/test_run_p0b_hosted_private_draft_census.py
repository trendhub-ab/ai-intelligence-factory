from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run_p0b_hosted_private_draft_census as census

ROOT = Path(__file__).resolve().parents[1]


class P0BHostedPrivateDraftCensusTests(unittest.TestCase):
    def test_decision_requires_strong_zero_for_retry_candidate(self) -> None:
        self.assertEqual(census._classify_census(0, 0, 0), "strong_zero")
        self.assertEqual(census._classify_census(1, 0, 0), "single_exact")

    def test_any_uncertainty_remains_ambiguous(self) -> None:
        cases = [
            (2, 0, 0),
            (0, 1, 0),
            (1, 1, 0),
            (0, 0, 1),
            (1, 0, 1),
        ]
        for exact, suspicious, unreadable in cases:
            with self.subTest(exact=exact, suspicious=suspicious, unreadable=unreadable):
                self.assertEqual(census._classify_census(exact, suspicious, unreadable), "ambiguous")

    def test_census_uses_proven_draft_filter_navigation_before_anchor_enumeration(self) -> None:
        source = inspect.getsource(census.census)
        open_pos = source.index("nav.menu._open_status_filter_menu(page)")
        select_pos = source.index("nav._select_unique_draft_filter(page)")
        anchor_pos = source.index('anchors = page.locator("a[href]")')
        self.assertLess(open_pos, select_pos)
        self.assertLess(select_pos, anchor_pos)

    def test_probe_is_read_only_and_uses_article_list_only(self) -> None:
        source = inspect.getsource(census.census)
        self.assertIn("ARTICLE_LIST_URL", source)
        self.assertIn("_looks_logged_out", source)
        for forbidden in (".click(", ".fill(", ".type(", ".press(", "editor.note.com/new"):
            self.assertNotIn(forbidden, source)

    def test_result_schema_is_safe_aggregate_only(self) -> None:
        self.assertEqual(
            census.SAFE_RESULT_KEYS,
            {
                "status",
                "authenticated",
                "private_note_card_count",
                "exact_target_count",
                "suspicious_blank_count",
                "unreadable_count",
                "decision",
                "zero_model_calls",
                "mutation_count",
            },
        )

    def test_workflow_is_hosted_read_only_and_ledger_gated(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "p0b-hosted-private-draft-census.yml").read_text(encoding="utf-8")
        self.assertIn("ops/p0b-hosted-b01-recovery-20261006", workflow)
        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertIn("note_delivery_ledger_preflight.sh", workflow)
        self.assertIn("ledger_blocked_ambiguous", workflow)
        self.assertIn("NOTE_STORAGE_STATE_B64", workflow)
        self.assertIn("run_p0b_hosted_private_draft_census.py", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("GCP_NOTE_VM", workflow)
        self.assertNotIn("actions: write", workflow)
        self.assertNotIn("gh workflow run", workflow)
        self.assertNotIn("PATCH", workflow)
        self.assertNotIn("DELETE", workflow)


if __name__ == "__main__":
    unittest.main()
