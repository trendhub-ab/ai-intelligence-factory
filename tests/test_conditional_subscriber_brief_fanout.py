from __future__ import annotations

import unittest
from pathlib import Path

import daily_portfolio_review as product_review


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class ConditionalSubscriberBriefFanoutTests(unittest.TestCase):
    def test_product_review_exposes_subscriber_change_receipt(self) -> None:
        change_count = getattr(product_review, "subscriber_change_count", None)
        self.assertIsNotNone(
            change_count,
            "daily_portfolio_review must expose subscriber_change_count",
        )
        self.assertEqual(
            4,
            change_count(
                {
                    "subscriber_sync": {
                        "created": 1,
                        "updated": 1,
                        "archived": 1,
                        "unchanged": 9,
                    },
                    "subscriber_updated": 1,
                }
            ),
        )
        self.assertEqual(
            0,
            change_count(
                {
                    "subscriber_sync": {
                        "created": 0,
                        "updated": 0,
                        "archived": 0,
                        "unchanged": 10,
                    },
                    "subscriber_updated": 0,
                }
            ),
        )

    def test_one_shot_dispatches_subscriber_brief_only_on_change_receipt(self) -> None:
        text = (WORKFLOWS / "daily-one-shot.yml").read_text(encoding="utf-8")
        self.assertIn("id: product_review", text)
        self.assertIn(
            "SUBSCRIBER_CHANGES_DETECTED: ${{ steps.product_review.outputs.subscriber_changes_detected }}",
            text,
        )
        self.assertIn(
            'if [ "${SUBSCRIBER_CHANGES_DETECTED:-false}" = "true" ]; then',
            text,
        )
        self.assertIn("gh workflow run subscriber-decision-brief.yml --ref main", text)
        self.assertNotIn(
            "for target in subscriber-decision-brief.yml cross-db-contract-guard.yml",
            text,
        )
        self.assertIn("gh workflow run cross-db-contract-guard.yml --ref main", text)


if __name__ == "__main__":
    unittest.main()
