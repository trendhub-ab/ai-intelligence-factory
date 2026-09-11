import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from x_discovery.bounded_calibration_validation import (
    BoundedCalibrationError,
    build_calibration_item,
    run_calibration_boundary,
)


CANDIDATE = Path("x_discovery/fixtures/defense_factory_boundary_20260911.json")
SCREENING = Path("x_discovery/fixtures/defense_factory_screening_result_20260911.json")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class FakePipeline:
    ENABLE_GLOBAL_CALIBRATION = True
    GLOBAL_CALIBRATION_MIN_RAW_SCORE = 55

    def __init__(self):
        self.prompt_calls = 0
        self.provider_calls = 0
        self.write_calls = 0

    def _calibration_prompt(self, batch):
        self.prompt_calls += 1
        self.asserted_batch = batch
        return "calibrate exactly one saved candidate"

    def _generate_via_chat(self, *_args, **_kwargs):
        self.provider_calls += 1
        raise AssertionError("provider must not be called by calibration boundary")

    def save_to_notion(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("Notion must not be called by calibration boundary")


class XBoundedCalibrationValidationTests(unittest.TestCase):
    def test_reaches_real_calibration_prompt_boundary_without_provider_or_write(self):
        fake = FakePipeline()
        result = run_calibration_boundary(fake, load(CANDIDATE), load(SCREENING))
        self.assertEqual(result["status"], "CALIBRATION_BOUNDARY_READY")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["raw_score"], 88)
        self.assertEqual(result["operation_model_request_ceiling"], 1)
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["calibration_executed"])
        self.assertFalse(result["stock_persisted"])
        self.assertFalse(result["deep_dive_selected"])
        self.assertEqual(fake.prompt_calls, 1)
        self.assertEqual(fake.provider_calls, 0)
        self.assertEqual(fake.write_calls, 0)
        item = fake.asserted_batch[0]
        self.assertEqual(item["screening_id"], "X0001")
        self.assertEqual(item["raw_score"], 88)
        self.assertIsNone(item["final_score"])
        self.assertIsNone(item["notion_page_id"])

    def test_saved_screening_and_candidate_provenance_must_match(self):
        screening = load(SCREENING)
        screening["observation_provenance"]["x_post_id"] = "wrong"
        with self.assertRaisesRegex(BoundedCalibrationError, "X provenance"):
            build_calibration_item(load(CANDIDATE), screening)

    def test_saved_screening_cannot_authorize_model_calls(self):
        screening = load(SCREENING)
        screening["model_calls_allowed"] = 1
        with self.assertRaisesRegex(BoundedCalibrationError, "must not authorize"):
            build_calibration_item(load(CANDIDATE), screening)

    def test_disabled_calibration_fails_closed(self):
        fake = FakePipeline()
        fake.ENABLE_GLOBAL_CALIBRATION = False
        with self.assertRaisesRegex(BoundedCalibrationError, "must be enabled"):
            run_calibration_boundary(fake, load(CANDIDATE), load(SCREENING))
        self.assertEqual(fake.provider_calls, 0)

    def test_score_below_live_threshold_fails_closed(self):
        fake = FakePipeline()
        fake.GLOBAL_CALIBRATION_MIN_RAW_SCORE = 90
        with self.assertRaisesRegex(BoundedCalibrationError, "below Calibration threshold"):
            run_calibration_boundary(fake, load(CANDIDATE), load(SCREENING))
        self.assertEqual(fake.provider_calls, 0)


if __name__ == "__main__":
    unittest.main()
