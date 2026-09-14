import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_DIR = ROOT / "x_discovery" / "watchlists"


class XWatchlistPolicyTests(unittest.TestCase):
    def test_core_watchlist_stays_exactly_twenty_unique_accounts(self):
        data = json.loads((WATCHLIST_DIR / "ai_core_20.json").read_text(encoding="utf-8"))
        handles = [row["handle"] for row in data["accounts"]]
        self.assertEqual(len(handles), 20)
        self.assertEqual(len({handle.lower() for handle in handles}), 20)

    def test_candidate_registry_is_inert_and_exactly_thirty_unique_accounts(self):
        data = json.loads((WATCHLIST_DIR / "ai_candidate_30.json").read_text(encoding="utf-8"))
        accounts = data["accounts"]
        handles = [row["handle"] for row in accounts]

        self.assertEqual(data["expected_account_count"], 30)
        self.assertFalse(data["monitoring_enabled"])
        self.assertTrue(data["activation_policy"]["requires_manual_promotion"])
        self.assertEqual(len(accounts), 30)
        self.assertEqual(len({handle.lower() for handle in handles}), 30)
        self.assertTrue(all(row["monitoring_enabled"] is False for row in accounts))
        self.assertTrue(
            all(row["verification_status"] == "preactivation_review_required" for row in accounts)
        )

    def test_bootstrap_workflow_cannot_consume_candidate_registry(self):
        workflow = (ROOT / ".github" / "workflows" / "x-discovery-bootstrap.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("x_discovery/watchlists/ai_core_20.json", workflow)
        self.assertNotIn("ai_candidate_30.json", workflow)
        self.assertIn("exactly 20 unique handles", workflow)
        self.assertIn("Bootstrap must contain exactly 20 handles", workflow)


if __name__ == "__main__":
    unittest.main()
