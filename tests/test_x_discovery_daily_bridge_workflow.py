from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "x-discovery-stage2-smoke.yml"


class XDiscoveryDailyBridgeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_live_bridge_is_manual_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)
        self.assertNotIn("\n  push:", self.text)

    def test_no_gemini_or_production_write_credentials_are_exposed(self):
        forbidden_secret_bindings = (
            "${{ secrets.GEMINI_API_KEY }}",
            "${{ secrets.GOOGLE_API_KEY }}",
            "${{ secrets.NOTION_API_KEY }}",
            "${{ secrets.NOTION_DECISION_INTELLIGENCE_API_KEY }}",
            "${{ secrets.TELEGRAM_BOT_TOKEN }}",
        )
        for binding in forbidden_secret_bindings:
            with self.subTest(binding=binding):
                self.assertNotIn(binding, self.text)
        self.assertNotIn("python production_pipeline.py", self.text)
        self.assertNotIn("python pipeline.py", self.text)

    def test_live_x_transport_reaches_only_inert_factory_adapter(self):
        self.assertIn("python -m x_discovery.runner", self.text)
        self.assertIn("--provider apify", self.text)
        self.assertIn("isolateProfiles", self.text)
        self.assertIn("python -m x_discovery.factory_adapter", self.text)
        self.assertIn("adapter['factory_write'] is False", self.text)
        self.assertIn("adapter['screening_executed'] is False", self.text)
        self.assertIn("adapter['evidence_promoted'] is False", self.text)
        self.assertIn("manifest['x_official_api_calls'] == 0", self.text)

    def test_apify_charge_and_watchlist_bounds_remain_fixed(self):
        self.assertIn("APIFY_MAX_CHARGE_USD: '0.05'", self.text)
        self.assertIn("MAX_RECORDS: '100'", self.text)
        self.assertIn("len(payload.get('handles', [])) != 20", self.text)
        self.assertIn("payload.get('maxPosts') != 5", self.text)
        self.assertIn("payload.get('onlyPostsNewerThan') != '12 hours'", self.text)


if __name__ == "__main__":
    unittest.main()
