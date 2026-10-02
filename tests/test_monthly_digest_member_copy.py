from datetime import date
import unittest

from content_generation_protocol import build_monthly_digest_markdown


class MonthlyDigestMemberCopyTests(unittest.TestCase):
    def test_digest_hides_internal_stage_scores_from_member_copy(self):
        items = [
            {"name": "Ready", "url": "https://example.com/ready", "score": 95,
             "source": "GitHub", "status": "DEEP", "article_status": "READY"},
            {"name": "Stock", "url": "https://example.com/stock", "score": 88,
             "source": "ArXiv", "status": "STOCK", "article_status": ""},
        ]
        text = build_monthly_digest_markdown(
            date(2026, 10, 1),
            items,
            STATUS_DEEP_DIVE="DEEP",
            ARTICLE_STATUS_READY="READY",
            STATUS_STOCKED="STOCK",
        )
        self.assertIn("今月、まず読む記事", text)
        self.assertIn("あとで探せる新着", text)
        self.assertIn("今月の収録状況", text)
        self.assertIn("[Ready]", text)
        self.assertIn("[Stock]", text)
        for token in ("Step1", "Step2", "Decision Score", "95点", "88点", "PROP_STATUS"):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
