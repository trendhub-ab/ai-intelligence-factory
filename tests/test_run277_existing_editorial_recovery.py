import unittest
from types import SimpleNamespace
from unittest import mock

import article_revalidation


class _Response:
    def __init__(self, status_code=200, article_status="", content_status=""):
        self.status_code = status_code
        self._payload = {
            "properties": {
                "Article Status": {"select": {"name": article_status}},
                "Content Status": {"select": {"name": content_status}},
            }
        }

    def json(self):
        return self._payload


class _Budget:
    def __init__(self, allowed=True, budget=12):
        self.allowed = allowed
        self.budget = budget

    def can_request(self):
        return self.allowed


class _DailyQuotaExhaustedError(Exception):
    pass


def _row(page_id, name):
    return {
        "notion_page_id": page_id,
        "screening_score": 80,
        "screening_reason": "reason",
        "repo": {
            "nameWithOwner": name,
            "url": f"https://example.com/{name}",
            "source": "OfficialVendor",
        },
    }


def _pipeline(rows, statuses, *, global_allowed=True, deep_allowed=True):
    calls = []

    def get(url, headers=None, timeout=None):
        page_id = url.rsplit("/", 1)[-1]
        value = statuses.get(page_id)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return _Response(status_code=500)
        return _Response(200, *value)

    def generate(repo, **kwargs):
        calls.append((repo, kwargs))
        return "ready manuscript"

    pipeline = SimpleNamespace(
        requests=SimpleNamespace(get=get),
        logger=mock.Mock(),
        _notion_headers=lambda: {},
        PROP_ARTICLE_STATUS="Article Status",
        PROP_CONTENT_STATUS="Content Status",
        ARTICLE_STATUS_READY="Ready",
        ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW="Needs Editorial Review",
        CONTENT_STATUS_PENDING_RETRY="Pending Retry",
        CONTENT_STATUS_QUALITY_FAILED="Quality Failed",
        get_regen_test_items=lambda limit, source: list(rows),
        TOP_N_FOR_DEEP_DIVE=3,
        NOTION_API_KEY="token",
        GEMINI_BUDGET=_Budget(global_allowed),
        DEEP_DIVE_MODEL_BUDGET=_Budget(deep_allowed),
        DEEP_DIVE_MODEL_POOL=("m1",),
        _model_pool_has_session_candidate=lambda pool: True,
        legal_safety_gate=lambda repo: (True, "safe"),
        generate_intelligence_report=generate,
        DailyQuotaExhaustedError=_DailyQuotaExhaustedError,
    )
    return pipeline, calls


class ExistingNonReadySelectionTests(unittest.TestCase):
    def test_readonly_validation_can_select_editorial_and_quality_failed_but_not_ready_or_pending(self):
        rows = [_row("e", "editorial"), _row("q", "quality"), _row("r", "ready"), _row("p", "pending")]
        statuses = {
            "e": ("Needs Editorial Review", "Deep Dive"),
            "q": ("Not Planned", "Quality Failed"),
            "r": ("Ready", "Deep Dive"),
            "p": ("Not Planned", "Pending Retry"),
        }
        pipeline, _ = _pipeline(rows, statuses)
        selected = article_revalidation.select_revalidation_items(pipeline, limit=10)
        self.assertEqual([x["notion_page_id"] for x in selected], ["e", "q"])

    def test_full_recovery_selection_excludes_quality_failed(self):
        rows = [_row("q", "quality"), _row("e", "editorial")]
        statuses = {
            "q": ("Not Planned", "Quality Failed"),
            "e": ("Needs Editorial Review", "Deep Dive"),
        }
        pipeline, _ = _pipeline(rows, statuses)
        selected = article_revalidation.select_revalidation_items(
            pipeline, limit=10, include_quality_failed=False
        )
        self.assertEqual([x["notion_page_id"] for x in selected], ["e"])

    def test_status_read_failure_fails_closed_for_that_candidate(self):
        rows = [_row("broken", "broken"), _row("e", "editorial")]
        statuses = {
            "broken": RuntimeError("notion unavailable"),
            "e": ("Needs Editorial Review", "Deep Dive"),
        }
        pipeline, _ = _pipeline(rows, statuses)
        selected = article_revalidation.select_revalidation_items(
            pipeline, limit=10, include_quality_failed=False
        )
        self.assertEqual([x["notion_page_id"] for x in selected], ["e"])


class ExistingEditorialRecoveryTests(unittest.TestCase):
    def test_recovery_reuses_existing_page_and_persists_at_most_one_editorial_row(self):
        rows = [_row("e1", "editorial-1"), _row("e2", "editorial-2"), _row("q", "quality")]
        statuses = {
            "e1": ("Needs Editorial Review", "Deep Dive"),
            "e2": ("Needs Editorial Review", "Deep Dive"),
            "q": ("Not Planned", "Quality Failed"),
        }
        pipeline, calls = _pipeline(rows, statuses)
        generated, rank = article_revalidation.run_existing_editorial_recovery(
            pipeline, generated_count=1, next_candidate_rank=7, limit=99
        )
        self.assertEqual((generated, rank), (2, 8))
        self.assertEqual(len(calls), 1)
        repo, kwargs = calls[0]
        self.assertEqual(repo["nameWithOwner"], "editorial-1")
        self.assertEqual(kwargs["notion_page_id"], "e1")
        self.assertEqual(kwargs["candidate_origin"], "existing_editorial_recovery")
        self.assertTrue(kwargs["persist_results"])
        self.assertEqual(kwargs["candidate_rank"], 8)

    def test_target_already_met_skips_selection_and_gemini(self):
        pipeline, calls = _pipeline([], {})
        pipeline.get_regen_test_items = mock.Mock(side_effect=AssertionError("must not read recovery candidates"))
        generated, rank = article_revalidation.run_existing_editorial_recovery(
            pipeline, generated_count=3, next_candidate_rank=4
        )
        self.assertEqual((generated, rank), (3, 4))
        pipeline.get_regen_test_items.assert_not_called()
        self.assertEqual(calls, [])

    def test_exhausted_existing_budget_skips_before_candidate_read(self):
        pipeline, calls = _pipeline([], {}, deep_allowed=False)
        pipeline.get_regen_test_items = mock.Mock(side_effect=AssertionError("must not read when budget is exhausted"))
        generated, rank = article_revalidation.run_existing_editorial_recovery(
            pipeline, generated_count=0, next_candidate_rank=2
        )
        self.assertEqual((generated, rank), (0, 2))
        pipeline.get_regen_test_items.assert_not_called()
        self.assertEqual(calls, [])

    def test_failed_generation_does_not_increment_ready_count(self):
        rows = [_row("e", "editorial")]
        statuses = {"e": ("Needs Editorial Review", "Deep Dive")}
        pipeline, calls = _pipeline(rows, statuses)
        pipeline.generate_intelligence_report = mock.Mock(return_value=None)
        generated, rank = article_revalidation.run_existing_editorial_recovery(
            pipeline, generated_count=0, next_candidate_rank=0
        )
        self.assertEqual((generated, rank), (0, 1))
        pipeline.generate_intelligence_report.assert_called_once()

    def test_install_wrapper_preserves_backlog_first_then_recovery_order(self):
        events = []

        def backlog(pending_items, generated_count, next_candidate_rank):
            events.append("backlog")
            return generated_count + 1, next_candidate_rank + 2

        pipeline = SimpleNamespace(process_article_backlog=backlog)
        with mock.patch.object(
            article_revalidation,
            "run_existing_editorial_recovery",
            side_effect=lambda p, g, r, limit: (events.append(("recovery", g, r)) or (g, r)),
        ):
            article_revalidation.install_full_recovery(pipeline)
            result = pipeline.process_article_backlog([], 0, 10)
        self.assertEqual(result, (1, 12))
        self.assertEqual(events, ["backlog", ("recovery", 1, 12)])


if __name__ == "__main__":
    unittest.main()
