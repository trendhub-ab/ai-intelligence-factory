import unittest
from types import SimpleNamespace

from x_discovery.post_calibration_dry_run import (
    PostCalibrationDryRunError,
    audit_post_calibration_counterexamples,
)


def policy(**overrides):
    values = {
        "NOTION_SAVE_THRESHOLD_SCORE": 60,
        "TOP_N_FOR_DEEP_DIVE": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class XPostCalibrationDryRunTests(unittest.TestCase):
    def test_threshold_and_persistence_guards_hold(self):
        result = audit_post_calibration_counterexamples(policy())
        self.assertEqual(result["status"], "POST_CALIBRATION_GUARDS_VERIFIED")
        self.assertEqual(result["stock_threshold"], 60)
        cases = result["cases"]
        self.assertFalse(cases["below_threshold_unpersisted"]["deep_dive_selected"])
        self.assertFalse(cases["at_threshold_unpersisted"]["deep_dive_selected"])
        self.assertTrue(cases["at_threshold_persisted_simulation"]["deep_dive_selected"])
        self.assertFalse(cases["defense_88_unpersisted"]["deep_dive_selected"])
        self.assertTrue(cases["defense_88_persisted_simulation"]["deep_dive_selected"])
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["notion_calls"], 0)
        self.assertFalse(result["factory_write"])

    def test_threshold_change_is_read_from_live_policy(self):
        result = audit_post_calibration_counterexamples(policy(NOTION_SAVE_THRESHOLD_SCORE=70))
        self.assertEqual(result["stock_threshold"], 70)
        self.assertEqual(result["cases"]["below_threshold_unpersisted"]["final_score"], 69)
        self.assertEqual(result["cases"]["at_threshold_unpersisted"]["final_score"], 70)
        self.assertTrue(result["cases"]["defense_88_persisted_simulation"]["deep_dive_selected"])

    def test_invalid_stock_threshold_fails_closed(self):
        with self.assertRaisesRegex(PostCalibrationDryRunError, "NOTION_SAVE_THRESHOLD_SCORE"):
            audit_post_calibration_counterexamples(policy(NOTION_SAVE_THRESHOLD_SCORE=0))

    def test_invalid_top_n_fails_closed(self):
        with self.assertRaisesRegex(PostCalibrationDryRunError, "TOP_N_FOR_DEEP_DIVE"):
            audit_post_calibration_counterexamples(policy(TOP_N_FOR_DEEP_DIVE=0))


if __name__ == "__main__":
    unittest.main()
