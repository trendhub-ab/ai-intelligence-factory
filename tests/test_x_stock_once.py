import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from x_discovery.stock_once import OPERATION, REPOSITORY, StockOnceError, run_once


class StockOnceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path("x_discovery")
        cls.candidate = json.loads((root / "fixtures/defense_factory_boundary_20260911.json").read_text())
        cls.observation = json.loads((root / "observations/defense_factory_calibration_20260911.json").read_text())

    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIIF_X_STOCK_OPERATION": OPERATION, "GITHUB_RUN_ATTEMPT": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.claims = self.writes = 0

    def pipeline(self, existing=(), write_result="page-1"):
        p = NS(NOTION_SAVE_THRESHOLD_SCORE=60, NOTION_API_KEY="fake",
               NOTION_DATA_SOURCE_ID="db", NOTION_DATABASE_ID="",
               GH_PAT="fake", GEMINI_BUDGET=NS(request_count=0),
               PERSISTENT_GEMINI_COUNTER=NS(branch="runtime-state", repo=REPOSITORY),
               send_telegram_alert=lambda *a, **k: None)
        p.get_existing_repo_urls = lambda: set(existing)
        def save(repo, score, reason):
            self.writes += 1
            self.assertEqual(repo["source"], "OfficialVendor")
            self.assertEqual(score, 88)
            self.assertNotIn("x_discovery_provenance", repo)
            self.assertIn("x_discovery_provenance", repo["sourceDetails"])
            return write_result
        p.save_screening_metadata_to_notion = save
        return p

    def claim(self, *args):
        if self.claims:
            raise StockOnceError("already claimed")
        self.claims += 1

    def test_one_stock_write_and_no_deep_dive(self):
        result = run_once(self.pipeline(), self.candidate, self.observation, self.claim)
        self.assertEqual(result["status"], "STOCK_SAVED")
        self.assertEqual(result["notion_writes"], 1)
        self.assertTrue(result["stock_persisted"])
        self.assertFalse(result["deep_dive_selected"])
        self.assertEqual((self.claims, self.writes), (1, 1))

    def test_existing_url_stops_before_claim_and_write(self):
        p = self.pipeline(existing={"https://openai.com/the-defense-factory/"})
        with self.assertRaisesRegex(StockOnceError, "already exists"):
            run_once(p, self.candidate, self.observation, self.claim)
        self.assertEqual((self.claims, self.writes), (0, 0))

    def test_failed_or_ambiguous_write_is_not_retried(self):
        with self.assertRaisesRegex(StockOnceError, "no retry"):
            run_once(self.pipeline(write_result=None), self.candidate, self.observation, self.claim)
        self.assertEqual((self.claims, self.writes), (1, 1))

    def test_rerun_stops_before_read_claim_write(self):
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        p = self.pipeline()
        p.get_existing_repo_urls = lambda: self.fail("dedup read must not run")
        with self.assertRaisesRegex(StockOnceError, "reruns"):
            run_once(p, self.candidate, self.observation, self.claim)
        self.assertEqual((self.claims, self.writes), (0, 0))

    def test_tampered_final_stops(self):
        observation = dict(self.observation, final_score=89)
        with self.assertRaisesRegex(StockOnceError, "final_score"):
            run_once(self.pipeline(), self.candidate, observation, self.claim)
        self.assertEqual((self.claims, self.writes), (0, 0))

    def test_production_entrypoint_routes_before_preflight(self):
        source = Path("production_pipeline.py").read_text()
        lane = source.index('if mode == "x_saved_candidate_stock_once":')
        preflight = source.index("runtime_state_channel.preflight_runtime_state_channel()", lane)
        self.assertLess(lane, preflight)
        scoped = source[lane:preflight]
        self.assertIn("run_from_paths(pipeline, Path(candidate_path), Path(observation_path))", scoped)
        self.assertNotIn("pipeline.main()", scoped)


if __name__ == "__main__":
    unittest.main()
