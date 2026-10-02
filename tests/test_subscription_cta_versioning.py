import pathlib
import unittest

import note_manuscript
import subscription_attribution


class SubscriptionCtaVersioningTests(unittest.TestCase):
    def test_versioned_cta_renders_same_public_copy(self):
        url = "https://example.com/membership?aif_article_id=aif-test"
        rendered = note_manuscript.build_subscription_cta("aif-test", url)
        self.assertIn("### 調査と判断の時間を減らしたい方へ", rendered)
        self.assertIn("無料記事では重要テーマを最後まで公開しています。", rendered)
        self.assertIn("[会員向け意思決定DB＋月次サマリーを見る]", rendered)
        self.assertEqual(note_manuscript.SUBSCRIPTION_CTA_COPY_ID, "decision-db-summary-v1")

    def test_rollup_groups_by_cta_copy_version(self):
        manifests = {
            "a": {
                "article_id": "a",
                "source": "GitHub",
                "portfolio_topic": "DEVTOOLS",
                "cta_copy_id": "decision-db-summary-v1",
            },
            "b": {
                "article_id": "b",
                "source": "ArXiv",
                "portfolio_topic": "RESEARCH",
            },
        }
        rows = [
            {"article_id": "a", "attribution_method": "tracked_cta", "note_views": 100, "cta_clicks": 10,
             "new_subscribers": None, "retained_subscribers": None, "subscription_revenue_yen": None},
            {"article_id": "b", "attribution_method": "tracked_cta", "note_views": 50, "cta_clicks": 2,
             "new_subscribers": None, "retained_subscribers": None, "subscription_revenue_yen": None},
        ]
        rollup = subscription_attribution.build_rollup(manifests, rows)
        keys = {row["cta_copy_id"] for row in rollup["performance_by_cta_copy"]}
        self.assertEqual(keys, {"decision-db-summary-v1", "legacy_unversioned"})


if __name__ == "__main__":
    unittest.main()
