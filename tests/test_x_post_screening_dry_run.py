import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from x_discovery.post_screening_dry_run import (
    PostScreeningDryRunError,
    audit_post_screening_route,
)


FIXTURE = Path("x_discovery/fixtures/defense_factory_screening_result_20260911.json")


def pipeline_policy(**overrides):
    values = {
        "NOTION_SAVE_THRESHOLD_SCORE": 60,
        "ENABLE_GLOBAL_CALIBRATION": True,
        "GLOBAL_CALIBRATION_MIN_RAW_SCORE": 55,
        "TOP_N_FOR_DEEP_DIVE": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class XPostScreeningDryRunTests(unittest.TestCase):
    def test_real_observation_requires_calibration_and_stops_before_stock(self):
        result = audit_post_screening_route(pipeline_policy(), payload())
        self.assertEqual(result["raw_score"], 88)
        self.assertTrue(result["raw_stock_threshold_pass"])
        self.assertTrue(result["calibration_required"])
        self.assertEqual(result["status"], "CALIBRATION_REQUIRED")
        self.assertIsNone(result["final_score"])
        self.assertEqual(result["stock_route"], "DEFERRED_PENDING_CALIBRATION")
        self.assertFalse(result["stock_persisted"])
        self.assertFalse(result["deep_dive_selected"])
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["factory_write"])

    def test_calibration_disabled_shows_only_conditional_post_persistence_eligibility(self):
        result = audit_post_screening_route(
            pipeline_policy(ENABLE_GLOBAL_CALIBRATION=False), payload()
        )
        self.assertFalse(result["calibration_required"])
        self.assertEqual(result["final_score"], 88)
        self.assertTrue(result["final_stock_threshold_pass"])
        self.assertEqual(result["stock_route"], "ELIGIBLE_AFTER_PERSISTENCE")
        self.assertEqual(
            result["deep_dive_route"],
            "ELIGIBLE_FOR_SELECTION_ONLY_AFTER_STOCK_PERSISTENCE",
        )
        self.assertFalse(result["deep_dive_selected"])

    def test_below_calibration_and_stock_threshold_is_not_eligible(self):
        data = payload()
        data["screening_result"]["score"] = 50
        result = audit_post_screening_route(pipeline_policy(), data)
        self.assertFalse(result["calibration_required"])
        self.assertFalse(result["raw_stock_threshold_pass"])
        self.assertEqual(result["stock_route"], "BELOW_STOCK_THRESHOLD")
        self.assertEqual(result["deep_dive_route"], "NOT_ELIGIBLE")

    def test_rejects_any_model_call_authorization(self):
        data = payload()
        data["model_calls_allowed"] = 1
        with self.assertRaisesRegex(PostScreeningDryRunError, "model_calls_allowed must be 0"):
            audit_post_screening_route(pipeline_policy(), data)

    def test_rejects_factory_write(self):
        data = payload()
        data["factory_write"] = True
        with self.assertRaisesRegex(PostScreeningDryRunError, "factory_write must be false"):
            audit_post_screening_route(pipeline_policy(), data)


if __name__ == "__main__":
    unittest.main()
