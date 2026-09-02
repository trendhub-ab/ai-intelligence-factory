import os
import types
import unittest
from unittest.mock import patch

import run208_reader_value_repair as run208


class Run208ReaderValueRepairTests(unittest.TestCase):
    def _pipeline(self, result=(False, "reader_value_review_no_retry")):
        pipeline = types.SimpleNamespace()
        pipeline.should_attempt_dynamic_retry = lambda rows, evidence, origin="new": result
        return pipeline

    def test_disabled_outside_fast_lane(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [{"message": "reader_value_review:dense_report_cluster", "severity": "REVIEW"}]
        with patch.dict(os.environ, {}, clear=True):
            allowed, reason = pipeline.should_attempt_dynamic_retry(rows, {"ok": True}, "pending_retry")
        self.assertFalse(allowed)
        self.assertEqual(reason, "reader_value_review_no_retry")

    def test_allows_one_repair_for_repairable_reader_only_pending_retry(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [
            {"message": "reader_value_review:dense_report_cluster", "severity": "REVIEW"},
            {"message": "reader_value_review:repetitive_insight", "severity": "REVIEW"},
        ]
        with patch.dict(os.environ, {run208.FAST_LANE_ENV: "1"}, clear=True):
            first = pipeline.should_attempt_dynamic_retry(rows, {"evidence": "present"}, "pending_retry")
            second = pipeline.should_attempt_dynamic_retry(rows, {"evidence": "present"}, "pending_retry")
        self.assertEqual(first, (True, "run208_reader_value_fast_lane_repair"))
        self.assertEqual(second, (False, "reader_value_review_no_retry"))

    def test_refuses_non_reader_blocker(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [
            {"message": "reader_value_review:dense_report_cluster", "severity": "REVIEW"},
            {"message": "primary_evidence_insufficient", "severity": "HARD"},
        ]
        with patch.dict(os.environ, {run208.FAST_LANE_ENV: "1"}, clear=True):
            allowed, _ = pipeline.should_attempt_dynamic_retry(rows, {"evidence": "present"}, "pending_retry")
        self.assertFalse(allowed)

    def test_refuses_nonrepairable_reader_reason(self):
        pipeline = self._pipeline()
        run208.install(pipeline)
        rows = [{"message": "reader_value_review:reader_delight_overclaim", "severity": "REVIEW"}]
        with patch.dict(os.environ, {run208.FAST_LANE_ENV: "1"}, clear=True):
            allowed, _ = pipeline.should_attempt_dynamic_retry(rows, {"evidence": "present"}, "pending_retry")
        self.assertFalse(allowed)

    def test_refuses_new_candidate_and_missing_evidence_context(self):
        rows = [{"message": "reader_value_review:dense_report_cluster", "severity": "REVIEW"}]
        with patch.dict(os.environ, {run208.FAST_LANE_ENV: "1"}, clear=True):
            pipeline = self._pipeline()
            run208.install(pipeline)
            self.assertFalse(pipeline.should_attempt_dynamic_retry(rows, {"evidence": "present"}, "new")[0])
            pipeline2 = self._pipeline()
            run208.install(pipeline2)
            self.assertFalse(pipeline2.should_attempt_dynamic_retry(rows, None, "pending_retry")[0])

    def test_preserves_original_true_decision(self):
        pipeline = self._pipeline((True, "hard_retry"))
        run208.install(pipeline)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(pipeline.should_attempt_dynamic_retry([], None, "new"), (True, "hard_retry"))


if __name__ == "__main__":
    unittest.main()
