from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gemini_transient_recovery as recovery
import pending_retry_validation as fast_lane


ROOT = Path(__file__).resolve().parents[1]


class Run207PendingRetryRepairReserveTests(unittest.TestCase):
    def _pipeline(self):
        unavailable = set()
        logger = Mock()

        def original(model_name, reason=""):
            unavailable.add((model_name, reason))

        return SimpleNamespace(
            SESSION_UNAVAILABLE_MODELS=set(),
            _mark_model_unavailable=original,
            logger=logger,
            recorded=unavailable,
        )

    def test_fast_lane_request_budget_is_bounded_to_three(self):
        env = {}
        result = fast_lane.prepare_fast_lane_env(env)
        self.assertIs(result, env)
        self.assertEqual(env["GEMINI_PENDING_RETRY_REQUEST_BUDGET"], "3")
        self.assertEqual(fast_lane.FAST_LANE_PENDING_RETRY_REQUEST_BUDGET, 3)

    def test_default_production_503_policy_remains_two_occurrences(self):
        pipeline = self._pipeline()
        recovery.install(pipeline)

        pipeline._mark_model_unavailable("gemini-3.7-flash", "503")
        self.assertEqual(pipeline.recorded, set())

        pipeline._mark_model_unavailable("gemini-3.7-flash", "503 Service Unavailable")
        self.assertIn(
            ("gemini-3.7-flash", "transient_503_cooldown:2"),
            pipeline.recorded,
        )

    def test_fast_lane_first_503_enters_run_local_cooldown(self):
        pipeline = self._pipeline()
        recovery.install(pipeline)
        recovery.configure_cooldown_threshold(
            pipeline,
            fast_lane.FAST_LANE_503_COOLDOWN_THRESHOLD,
        )

        pipeline._mark_model_unavailable("gemini-3.7-flash", "503")

        self.assertEqual(fast_lane.FAST_LANE_503_COOLDOWN_THRESHOLD, 1)
        self.assertIn(
            ("gemini-3.7-flash", "transient_503_cooldown:1"),
            pipeline.recorded,
        )

    def test_fast_lane_threshold_is_process_local(self):
        fast = self._pipeline()
        normal = self._pipeline()
        recovery.install(fast)
        recovery.install(normal)
        recovery.configure_cooldown_threshold(fast, 1)

        fast._mark_model_unavailable("m", "503")
        normal._mark_model_unavailable("m", "503")

        self.assertIn(("m", "transient_503_cooldown:1"), fast.recorded)
        self.assertEqual(normal.recorded, set())

    def test_invalid_threshold_fails_closed(self):
        pipeline = self._pipeline()
        recovery.install(pipeline)
        with self.assertRaises(ValueError):
            recovery.configure_cooldown_threshold(pipeline, 0)

    def test_fast_lane_pins_budget_before_pipeline_import(self):
        source = (ROOT / "pending_retry_validation.py").read_text(encoding="utf-8")
        prepare_index = source.index("    prepare_fast_lane_env()")
        pipeline_import_index = source.index("    import pipeline")
        self.assertLess(prepare_index, pipeline_import_index)
        self.assertIn(
            "gemini_transient_recovery.configure_cooldown_threshold(",
            source,
        )

    def test_prepare_fast_lane_env_overrides_stale_workflow_value_only_in_process(self):
        with patch.dict(
            os.environ,
            {"GEMINI_PENDING_RETRY_REQUEST_BUDGET": "2"},
            clear=True,
        ):
            fast_lane.prepare_fast_lane_env()
            self.assertEqual(os.environ["GEMINI_PENDING_RETRY_REQUEST_BUDGET"], "3")


if __name__ == "__main__":
    unittest.main()
