import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace

import x_discovery.bounded_factory_validation as bounded_validation
from x_discovery.bounded_factory_validation import (
    BoundedValidationError,
    run_bounded_validation,
    run_single_screening_validation,
    validate_saved_candidate,
)


class FakePipeline:
    def __init__(self, existing=None):
        self._existing = set() if existing is None else existing
        self.alerts = []
        self.prompt_calls = 0
        self.provider_calls = 0
        self.write_calls = 0
        self.GEMINI_BUDGET = SimpleNamespace(daily_budget=1, screening_retry_budget=0, request_count=0)
        self.SCREENING_MODEL_POOL = ["gemini-test"]
        self.GEMINI_API_KEY = "test-key"
        self.client = object()

    def send_telegram_alert(self, message):
        self.alerts.append(message)

    def get_existing_repo_urls(self):
        return self._existing

    def _batch_screening_prompt(self, batch):
        self.prompt_calls += 1
        assert len(batch) == 1
        assert batch[0]["screening_id"] == "X0001"
        assert batch[0]["repo"]["stargazerCount"] == 0
        return "screen exactly one saved candidate"

    def _register_gemini_usage_atexit(self):
        return None

    def _generate_via_chat(self, model_name, prompt, **kwargs):
        self.provider_calls += 1
        if self.provider_calls > 1:
            raise AssertionError("more than one provider call")
        self.GEMINI_BUDGET.request_count += 1
        return SimpleNamespace(text='[{"id":"X0001","score":81,"commercial_score":73,"shelf_life_score":78,"topic":"SECURITY","tracking_eligible":true,"tracking_reason":"継続監視価値あり","reason":"実務影響が大きい"}]')

    def _parse_batch_screening_response(self, text, expected_ids, include_diagnostic=False):
        self.assert_expected = expected_ids
        return ({"X0001": {
            "score": 81, "commercial_score": 73, "shelf_life_score": 78,
            "portfolio_topic": "SECURITY", "topic_valid": True,
            "tracking_eligible": True, "tracking_reason": "継続監視価値あり",
            "reason": "実務影響が大きい",
        }}, [], "")

    def persist_to_notion(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("Factory writes must never be called")


def payload(url="https://example.com/defense-factory"):
    return {
        "schema_version": 1,
        "lane": "x_saved_candidate_validation",
        "factory_write": False,
        "evidence_promoted": False,
        "candidate": {
            "canonical_url": url,
            "x_post_id": "2097786616311840853",
            "x_post_url": "https://x.com/example/status/2097786616311840853",
            "author": "example",
            "source_platform": "x",
            "source_role": "discovery_signal",
            "evidence_status": "discovery_only",
            "is_evidence": False,
            "factory_write": False,
        },
        "prepared_primary_source": {
            "url": url,
            "title": "Defense Factory",
            "text": "A" * 500,
        },
    }


class BoundedFactoryValidationTests(unittest.TestCase):
    def test_reaches_prompt_boundary_without_provider_or_write(self):
        fake = FakePipeline()
        result = run_bounded_validation(fake, payload())
        self.assertEqual(result["status"], "SCREENING_BOUNDARY_READY")
        self.assertEqual(result["candidate_count"], 1)
        self.assertTrue(result["dedup_verified"])
        self.assertFalse(result["screening_executed"])
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["source_fetch_calls"], 0)
        self.assertFalse(result["factory_write"])
        self.assertEqual(fake.prompt_calls, 1)
        self.assertEqual(fake.provider_calls, 0)
        self.assertEqual(fake.write_calls, 0)
        self.assertEqual(fake.alerts, [])

    def test_single_screening_executes_exactly_one_provider_request(self):
        fake = FakePipeline()
        result = run_single_screening_validation(fake, payload())
        self.assertEqual(result["status"], "SCREENING_VALIDATED")
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["score"], 81)
        self.assertEqual(result["portfolio_topic"], "SECURITY")
        self.assertEqual(fake.provider_calls, 1)
        self.assertEqual(fake.GEMINI_BUDGET.request_count, 1)
        self.assertEqual(fake.write_calls, 0)

    def test_single_screening_rejects_budget_above_one_before_provider(self):
        fake = FakePipeline()
        fake.GEMINI_BUDGET.daily_budget = 2
        with self.assertRaisesRegex(BoundedValidationError, "GEMINI_DAILY_REQUEST_BUDGET=1"):
            run_single_screening_validation(fake, payload())
        self.assertEqual(fake.provider_calls, 0)

    def test_single_screening_rejects_retry_budget_before_provider(self):
        fake = FakePipeline()
        fake.GEMINI_BUDGET.screening_retry_budget = 1
        with self.assertRaisesRegex(BoundedValidationError, "GEMINI_SCREENING_RETRY_BUDGET=0"):
            run_single_screening_validation(fake, payload())
        self.assertEqual(fake.provider_calls, 0)

    def test_single_screening_rejects_multi_model_pool_before_provider(self):
        fake = FakePipeline()
        fake.SCREENING_MODEL_POOL = ["one", "two"]
        with self.assertRaisesRegex(BoundedValidationError, "exactly one screening model"):
            run_single_screening_validation(fake, payload())
        self.assertEqual(fake.provider_calls, 0)

    def test_duplicate_is_fail_closed(self):
        fake = FakePipeline(existing={"https://example.com/defense-factory"})
        with self.assertRaisesRegex(BoundedValidationError, "already exists"):
            run_bounded_validation(fake, payload())
        self.assertEqual(fake.prompt_calls, 0)
        self.assertEqual(fake.provider_calls, 0)

    def test_dedup_read_failure_is_fail_closed_and_alert_suppressed(self):
        fake = FakePipeline(existing=None)
        fake._existing = None
        with self.assertRaisesRegex(BoundedValidationError, "deduplication could not be verified"):
            run_bounded_validation(fake, payload())
        self.assertEqual(fake.prompt_calls, 0)
        self.assertEqual(fake.alerts, [])

    def test_rejects_evidence_promotion(self):
        bad = payload()
        bad["candidate"]["is_evidence"] = True
        with self.assertRaisesRegex(BoundedValidationError, "is_evidence must be false"):
            validate_saved_candidate(bad)

    def test_rejects_primary_source_url_mismatch(self):
        bad = payload()
        bad["prepared_primary_source"]["url"] = "https://example.com/other"
        with self.assertRaisesRegex(BoundedValidationError, "must match"):
            validate_saved_candidate(bad)

    def test_rejects_short_saved_body(self):
        bad = payload()
        bad["prepared_primary_source"]["text"] = "too short"
        with self.assertRaisesRegex(BoundedValidationError, "too short"):
            validate_saved_candidate(bad)

    def test_lane_source_contains_no_http_or_persistence_call(self):
        source = inspect.getsource(bounded_validation)
        self.assertNotIn("call_screening_provider(", source)
        self.assertNotIn("persist_to_notion(", source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("_call_screening_pool(", source)
        self.assertNotIn("_call_model_pool(", source)

    def test_production_entrypoint_routes_lane_before_live_preflight(self):
        source = Path("production_pipeline.py").read_text(encoding="utf-8")
        lane = source.index('if mode == "x_saved_candidate_validation":')
        preflight = source.index("runtime_state_channel.preflight_runtime_state_channel()", lane)
        font_setup = source.index("run179_eyecatch_font_refinement.ensure_google_font_assets(", lane)
        self.assertLess(lane, preflight)
        self.assertLess(lane, font_setup)
        self.assertIn("run_from_path(pipeline, Path(candidate_path))", source[lane:preflight])


if __name__ == "__main__":
    unittest.main()
