import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from x_discovery.calibration_once import (
    BoundedCalibrationError, MODEL, OPERATION, REPOSITORY, claim_operation, run_once,
)


class OnceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIIF_X_CALIBRATION_OPERATION": OPERATION, "GITHUB_RUN_ATTEMPT": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        root = Path("x_discovery/fixtures")
        self.candidate = json.loads((root / "defense_factory_boundary_20260911.json").read_text())
        self.screening = json.loads((root / "defense_factory_screening_result_20260911.json").read_text())
        self.claims = 0
        self.calls = 0

    def pipeline(self, failure=None):
        p = NS(ENABLE_GLOBAL_CALIBRATION=True, GLOBAL_CALIBRATION_MIN_RAW_SCORE=55,
               NOTION_SAVE_THRESHOLD_SCORE=60,
               GH_PAT="fake", client=object(), SCREENING_MODEL_POOL=[MODEL],
               GEMINI_BUDGET=NS(daily_budget=1, request_count=0, screening_retry_budget=0),
               PERSISTENT_GEMINI_COUNTER=NS(enabled=True, branch="runtime-state",
                                            repo=REPOSITORY, counter_scope="fake"))
        p._calibration_prompt = lambda items: "canonical test prompt"
        def generate(*args, **kwargs):
            self.calls += 1
            p.GEMINI_BUDGET.request_count += 1
            self.assertEqual(kwargs["config"].http_options.retry_options.attempts, 1)
            self.assertTrue(kwargs["config"].automatic_function_calling.disable)
            if failure:
                raise failure
            return NS(text="response")
        p._generate_via_chat = generate
        p._parse_batch_screening_response = lambda *a, **k: (
            {"X0001": dict(score=60, commercial_score=70, shelf_life_score=80,
                            topic_valid=True, portfolio_topic="SECURITY")}, [], "")
        return p

    def claim(self, *args):
        if self.claims:
            raise BoundedCalibrationError("already claimed")
        self.claims += 1

    def test_fresh_process_cannot_reissue(self):
        result = run_once(self.pipeline(), self.candidate, self.screening, self.claim)
        self.assertEqual(result["final_score"], 60)
        self.assertFalse(result["stock_persisted"])
        self.assertFalse(result["deep_dive_selected"])
        with self.assertRaises(BoundedCalibrationError):
            run_once(self.pipeline(), self.candidate, self.screening, self.claim)
        self.assertEqual(self.calls, 1)

    def test_timeout_and_503_keep_claim(self):
        for error in (TimeoutError(), RuntimeError("503")):
            self.claims = self.calls = 0
            with self.assertRaises(type(error)):
                run_once(self.pipeline(error), self.candidate, self.screening, self.claim)
            with self.assertRaises(BoundedCalibrationError):
                run_once(self.pipeline(), self.candidate, self.screening, self.claim)
            self.assertEqual(self.calls, 1)

    def test_invalid_response_does_not_fall_back_to_raw(self):
        p = self.pipeline()
        p._parse_batch_screening_response = lambda *a, **k: ({}, ["X0001"], "missing")
        with self.assertRaisesRegex(BoundedCalibrationError, "no Final"):
            run_once(p, self.candidate, self.screening, self.claim)
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.claims, 1)

    def test_rerun_and_disabled_counter_stop_before_claim(self):
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        with self.assertRaises(BoundedCalibrationError):
            run_once(self.pipeline(), self.candidate, self.screening, self.claim)
        os.environ["GITHUB_RUN_ATTEMPT"] = "1"
        p = self.pipeline()
        p.PERSISTENT_GEMINI_COUNTER.enabled = False
        with self.assertRaises(BoundedCalibrationError):
            run_once(p, self.candidate, self.screening, self.claim)
        self.assertEqual((self.calls, self.claims), (0, 0))

    def test_concurrent_create_only_claim(self):
        lock = threading.Lock()
        writes = []
        def put(url, **kwargs):
            self.assertNotIn("sha", kwargs["json"])
            self.assertFalse(kwargs["allow_redirects"])
            with lock:
                status = 422 if writes else 201
                writes.append(status)
                return NS(status_code=status)
        def attempt(_):
            try:
                claim_operation(self.pipeline(), {}, put)
                return True
            except BoundedCalibrationError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(attempt, range(2))), 1)

    def test_ambiguous_claim_does_not_send_model(self):
        def fail(*args):
            raise TimeoutError("claim response lost")
        with self.assertRaises(TimeoutError):
            run_once(self.pipeline(), self.candidate, self.screening, fail)
        self.assertEqual(self.calls, 0)


if __name__ == "__main__":
    unittest.main()
