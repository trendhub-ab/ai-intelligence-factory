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

    def _result(self, *, attempted=0, passed=0, failed=0, not_generated=0, unverified=0):
        return {
            "attempted": attempted,
            "succeeded": passed,
            "quality_passed": passed,
            "quality_failed": failed,
            "not_generated": not_generated,
            "unverified": unverified,
        }

    def test_fast_lane_cost_ceiling_is_four_requests_with_one_repair_reserved(self):
        self.assertEqual(fast_lane.FAST_LANE_INITIAL_GENERATION_SEND_CEILING, 3)
        self.assertEqual(fast_lane.FAST_LANE_POST_GENERATION_REPAIR_RESERVE, 1)
        self.assertEqual(fast_lane.FAST_LANE_PENDING_RETRY_REQUEST_BUDGET, 4)
        env = {}
        fast_lane.prepare_fast_lane_env(env)
        self.assertEqual(env["GEMINI_PENDING_RETRY_REQUEST_BUDGET"], "4")
        self.assertEqual(env[fast_lane.FAST_LANE_ENV], "1")

    def test_reproduced_503_503_success_sequence_leaves_exactly_one_repair_request(self):
        initial_provider_sends = 3
        remaining = fast_lane.FAST_LANE_PENDING_RETRY_REQUEST_BUDGET - initial_provider_sends
        self.assertEqual(remaining, 1)
        self.assertEqual(remaining, fast_lane.FAST_LANE_POST_GENERATION_REPAIR_RESERVE)

    def test_fast_lane_article_attempt_ceiling_is_one(self):
        self.assertEqual(fast_lane.FAST_LANE_ARTICLE_ATTEMPT_LIMIT, 1)

    def test_first_503_remains_fast_lane_cooldown_threshold(self):
        self.assertEqual(fast_lane.FAST_LANE_503_COOLDOWN_THRESHOLD, 1)

    def test_priority_is_screening_score_descending_and_stable_on_ties(self):
        items = [
            {"id": "old-85", "screening_score": 85},
            {"id": "score-90", "screening_score": 90},
            {"id": "new-85", "screening_score": 85},
            {"id": "missing"},
        ]
        ranked = fast_lane.prioritize_pending_items(items)
        self.assertEqual([row["id"] for row in ranked], ["score-90", "old-85", "new-85", "missing"])

    def test_failed_first_article_never_falls_through_to_second_candidate(self):
        pipeline = self._pipeline([None, ("must-not-run", "accepted")])
        items = [
            {"notion_page_id": "p1", "screening_score": 90, "screening_reason": "a", "repo": {"nameWithOwner": "A"}},
            {"notion_page_id": "p2", "screening_score": 85, "screening_reason": "b", "repo": {"nameWithOwner": "B"}},
        ]

        result = fast_lane.run_pending_retry_lane(pipeline, items, success_target=1)

        self.assertEqual(result, self._result(attempted=1, not_generated=1))
        self.assertEqual(pipeline.generate_intelligence_report.call_count, 1)
        first = pipeline.generate_intelligence_report.call_args_list[0]
        self.assertEqual(first.args[0]["nameWithOwner"], "A")
        self.assertEqual(first.kwargs["candidate_origin"], "pending_retry")
        self.assertIs(first.kwargs["persist_results"], False)

    def test_rejected_manuscript_is_not_counted_as_success(self):
        pipeline = self._pipeline([("diagnostic manuscript", "rejected")])
        result = fast_lane.run_pending_retry_lane(
            pipeline,
            [{"screening_score": 90, "repo": {"nameWithOwner": "A"}}],
        )
        self.assertEqual(result, self._result(attempted=1, failed=1))
        self.assertEqual(pipeline.generate_intelligence_report.call_count, 1)

    def test_accepted_nonpersistent_manuscript_is_quality_pass_not_ready(self):
        pipeline = self._pipeline([("diagnostic manuscript", "accepted"), ("should-not-run", "accepted")])
        items = [
            {"notion_page_id": "p1", "screening_score": 90, "screening_reason": "a", "repo": {"nameWithOwner": "A"}},
            {"notion_page_id": "p2", "screening_score": 85, "screening_reason": "b", "repo": {"nameWithOwner": "B"}},
        ]

        result = fast_lane.run_pending_retry_lane(pipeline, items, success_target=1)

        self.assertEqual(result, self._result(attempted=1, passed=1))
        self.assertEqual(pipeline.generate_intelligence_report.call_count, 1)
        log_text = "\n".join(str(call) for call in pipeline.logger.info.call_args_list)
        self.assertIn("ready_persisted=false", log_text)

    def test_unknown_truthy_return_is_unverified_not_success(self):
        pipeline = self._pipeline([{"article": "legacy truthy return"}])
        result = fast_lane.run_pending_retry_lane(
            pipeline,
            [{"screening_score": 90, "repo": {"nameWithOwner": "A"}}],
        )
        self.assertEqual(result, self._result(attempted=1, unverified=1))

    def test_dedicated_pending_budget_blocks_provider_call(self):
        pipeline = self._pipeline([("unexpected", "accepted")])
        pipeline.PENDING_RETRY_REQUEST_BUDGET = _Budget(False)
        result = fast_lane.run_pending_retry_lane(
            pipeline,
            [{"screening_score": 99, "repo": {"nameWithOwner": "A"}}],
        )
        self.assertEqual(result, self._result())
        pipeline.generate_intelligence_report.assert_not_called()

    def test_no_available_model_blocks_provider_call(self):
        pipeline = self._pipeline([("unexpected", "accepted")])
        pipeline._model_pool_has_session_candidate = lambda pool: False
        result = fast_lane.run_pending_retry_lane(
            pipeline,
            [{"screening_score": 99, "repo": {"nameWithOwner": "A"}}],
        )
        self.assertEqual(result, self._result())
        pipeline.generate_intelligence_report.assert_not_called()

    def test_empty_backlog_is_zero_cost(self):
        pipeline = self._pipeline([])
        result = fast_lane.run_pending_retry_lane(pipeline, [])
        self.assertEqual(result, self._result())
        pipeline.generate_intelligence_report.assert_not_called()


if __name__ == "__main__":
    unittest.main()
