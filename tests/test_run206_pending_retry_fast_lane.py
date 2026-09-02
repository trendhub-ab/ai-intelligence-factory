from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import pending_retry_validation as fast_lane


class _Budget:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def can_request(self):
        return self.allowed


class Run206PendingRetryFastLaneTests(unittest.TestCase):
    def _pipeline(self, reports):
        generate = Mock(side_effect=list(reports))
        return SimpleNamespace(
            PENDING_RETRY_REQUEST_BUDGET=_Budget(True),
            DEEP_DIVE_MODEL_BUDGET=_Budget(True),
            GEMINI_BUDGET=_Budget(True),
            DEEP_DIVE_MODEL_POOL=["m1", "m2"],
            _model_pool_has_session_candidate=lambda pool: bool(pool),
            generate_intelligence_report=generate,
            logger=Mock(),
        )

    def test_priority_is_screening_score_descending_and_stable_on_ties(self):
        items = [
            {"id": "old-85", "screening_score": 85},
            {"id": "score-90", "screening_score": 90},
            {"id": "new-85", "screening_score": 85},
            {"id": "missing"},
        ]
        ranked = fast_lane.prioritize_pending_items(items)
        self.assertEqual([row["id"] for row in ranked], ["score-90", "old-85", "new-85", "missing"])

    def test_stops_immediately_after_first_success(self):
        pipeline = self._pipeline([None, {"article": "ready"}, {"article": "should-not-run"}])
        items = [
            {"notion_page_id": "p1", "screening_score": 90, "screening_reason": "a", "repo": {"nameWithOwner": "A"}},
            {"notion_page_id": "p2", "screening_score": 85, "screening_reason": "b", "repo": {"nameWithOwner": "B"}},
            {"notion_page_id": "p3", "screening_score": 80, "screening_reason": "c", "repo": {"nameWithOwner": "C"}},
        ]

        result = fast_lane.run_pending_retry_lane(pipeline, items, success_target=1)

        self.assertEqual(result, {"attempted": 2, "succeeded": 1})
        self.assertEqual(pipeline.generate_intelligence_report.call_count, 2)
        first = pipeline.generate_intelligence_report.call_args_list[0]
        self.assertEqual(first.args[0]["nameWithOwner"], "A")
        self.assertEqual(first.kwargs["candidate_origin"], "pending_retry")

    def test_dedicated_pending_budget_blocks_provider_call(self):
        pipeline = self._pipeline([{ "article": "unexpected" }])
        pipeline.PENDING_RETRY_REQUEST_BUDGET = _Budget(False)
        result = fast_lane.run_pending_retry_lane(
            pipeline,
            [{"screening_score": 99, "repo": {"nameWithOwner": "A"}}],
        )
        self.assertEqual(result, {"attempted": 0, "succeeded": 0})
        pipeline.generate_intelligence_report.assert_not_called()

    def test_no_available_model_blocks_provider_call(self):
        pipeline = self._pipeline([{ "article": "unexpected" }])
        pipeline._model_pool_has_session_candidate = lambda pool: False
        result = fast_lane.run_pending_retry_lane(
            pipeline,
            [{"screening_score": 99, "repo": {"nameWithOwner": "A"}}],
        )
        self.assertEqual(result, {"attempted": 0, "succeeded": 0})
        pipeline.generate_intelligence_report.assert_not_called()

    def test_empty_backlog_is_zero_cost(self):
        pipeline = self._pipeline([])
        result = fast_lane.run_pending_retry_lane(pipeline, [])
        self.assertEqual(result, {"attempted": 0, "succeeded": 0})
        pipeline.generate_intelligence_report.assert_not_called()


if __name__ == "__main__":
    unittest.main()
