import unittest

import conversion_copy_diagnostics as d


def article(article_id, views=None, clicks=None, subscribers=None, cta_copy_id="decision-db-summary-v1"):
    return {
        "article_id": article_id,
        "cta_copy_id": cta_copy_id,
        "metrics": {
            "note_views": views,
            "cta_clicks": clicks,
            "new_subscribers": subscribers,
            "retained_subscribers": None,
            "subscription_revenue_yen": None,
        },
        "cta_click_rate": (clicks / views) if views and clicks is not None else None,
        "subscriber_conversion_per_click": (subscribers / clicks) if clicks and subscribers is not None else None,
    }


class ConversionCopyDiagnosticsTests(unittest.TestCase):
    def base(self, articles):
        return {
            "ranking_feedback_enabled": False,
            "overall_cta_click_rate": 0.04,
            "overall_subscriber_conversion_per_click": 0.10,
            "articles": articles,
            "performance_by_source": [],
            "performance_by_topic": [],
            "performance_by_cta_copy": [],
        }

    def test_low_ctr_points_to_cta_not_lp(self):
        result = d.build_diagnostics(self.base([article("a", 1000, 5, 1)]))
        row = result["article_diagnostics"][0]
        self.assertEqual(row["state"], "CTA_COPY_OR_PLACEMENT")
        self.assertFalse(row["copy_mutation_permitted"])
        self.assertEqual(row["model_calls"], 0)

    def test_good_ctr_low_post_click_points_to_offer_or_lp(self):
        result = d.build_diagnostics(self.base([article("a", 1000, 50, 1)]))
        row = result["article_diagnostics"][0]
        self.assertEqual(row["state"], "OFFER_OR_LP")

    def test_missing_click_tracking_blocks_copy_judgment(self):
        result = d.build_diagnostics(self.base([article("a", 1000, None, None)]))
        self.assertEqual(result["article_diagnostics"][0]["state"], "TRACKING_GAP")

    def test_small_sample_does_not_trigger_copy_change(self):
        result = d.build_diagnostics(self.base([article("a", 20, 0, 0)]))
        self.assertEqual(result["article_diagnostics"][0]["state"], "INSUFFICIENT_DATA")

    def test_ranking_feedback_must_remain_disabled(self):
        rollup = self.base([article("a", 1000, 50, 5)])
        rollup["ranking_feedback_enabled"] = True
        with self.assertRaisesRegex(ValueError, "ranking feedback"):
            d.build_diagnostics(rollup)

    def test_output_never_auto_mutates_or_calls_models(self):
        result = d.build_diagnostics(self.base([article("a", 1000, 5, 0)]))
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["copy_mutation_permitted"])
        self.assertFalse(result["publication_mutation_permitted"])
        self.assertFalse(result["ranking_feedback_enabled"])


if __name__ == "__main__":
    unittest.main()
