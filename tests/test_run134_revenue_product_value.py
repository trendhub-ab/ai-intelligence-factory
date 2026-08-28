import unittest

import subscription_attribution as attrib


class Run134RevenueMeasurementTests(unittest.TestCase):
    def test_revenue_readiness_never_auto_enables_ranking(self):
        manifests = {}
        rows = []
        for i in range(25):
            article_id = f"a{i}"
            manifests[article_id] = {
                "article_id": article_id,
                "source": "GitHub",
                "portfolio_topic": "AGENT",
            }
            rows.append({
                "article_id": article_id,
                "attribution_method": "end_to_end",
                "note_url": "",
                "period_start": "",
                "period_end": "",
                "note_views": 300.0,
                "cta_clicks": 10.0,
                "new_subscribers": 1.0,
                "retained_subscribers": 1.0,
                "subscription_revenue_yen": 1980.0,
            })

        rollup = attrib.build_rollup(manifests, rows)
        readiness = rollup["revenue_measurement_readiness"]

        self.assertEqual("READY_FOR_HUMAN_REVENUE_REVIEW", readiness["measurement_status"])
        self.assertFalse(readiness["ranking_feedback_enabled"])
        self.assertFalse(readiness["auto_feedback_permitted"])
        self.assertEqual(2, rollup["schema_version"])
        self.assertEqual("GitHub", rollup["performance_by_source"][0]["source"])
        self.assertEqual("AGENT", rollup["performance_by_topic"][0]["portfolio_topic"])

    def test_revenue_readiness_reports_collection_blockers_on_small_sample(self):
        manifests = {
            "a": {
                "article_id": "a",
                "source": "ArXiv",
                "portfolio_topic": "MODEL",
            }
        }
        rows = [{
            "article_id": "a",
            "attribution_method": "note_dashboard_only",
            "note_url": "",
            "period_start": "",
            "period_end": "",
            "note_views": 100.0,
            "cta_clicks": None,
            "new_subscribers": None,
            "retained_subscribers": None,
            "subscription_revenue_yen": None,
        }]

        readiness = attrib.build_rollup(manifests, rows)["revenue_measurement_readiness"]

        self.assertEqual("COLLECTING", readiness["measurement_status"])
        self.assertTrue(any("new_subscribers" in blocker for blocker in readiness["blockers"]))
        self.assertFalse(readiness["ranking_feedback_enabled"])
        self.assertFalse(readiness["auto_feedback_permitted"])

    def test_rollup_remains_privacy_safe_and_diagnostic_only(self):
        manifests = {
            "a": {
                "article_id": "a",
                "source": "GitHub",
                "portfolio_topic": "DEVTOOLS",
            }
        }
        rows = [{
            "article_id": "a",
            "attribution_method": "tracked_cta",
            "note_url": "",
            "period_start": "",
            "period_end": "",
            "note_views": 1000.0,
            "cta_clicks": 100.0,
            "new_subscribers": None,
            "retained_subscribers": None,
            "subscription_revenue_yen": None,
        }]

        rollup = attrib.build_rollup(manifests, rows)

        self.assertEqual("aggregate metrics only; subscriber PII forbidden", rollup["privacy"])
        self.assertFalse(rollup["ranking_feedback_enabled"])
        self.assertIn("revenue_measurement_readiness", rollup)
        self.assertIn("performance_by_source", rollup)
        self.assertIn("performance_by_topic", rollup)


if __name__ == "__main__":
    unittest.main(verbosity=2)
