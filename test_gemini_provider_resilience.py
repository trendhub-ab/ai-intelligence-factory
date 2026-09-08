from __future__ import annotations

import contextlib
import types
import unittest
from unittest import mock

import gemini_provider_resilience as resilience


class FakeAPIError(Exception):
    def __init__(self, message: str, code=None, response=None):
        super().__init__(message)
        self.code = code
        self.response = response


class GeminiBudgetExceededError(Exception):
    pass


class GeminiCallTimeoutError(Exception):
    pass


class PendingRetryBudgetExceededError(Exception):
    pass


class DeepDiveRunBudgetExceededError(Exception):
    pass


class ProductReviewBudgetExceededError(Exception):
    pass


class NoAvailableModelError(Exception):
    pass


class Budget:
    def __init__(self, can_request=True, used=0, budget=12):
        self._can_request = can_request
        self.used = used
        self.budget = budget

    def can_request(self):
        return self._can_request

    def summary(self):
        return f"used={self.used}/{self.budget}"


class Logger:
    def __init__(self):
        self.rows = []

    def warning(self, message, *args):
        self.rows.append(message % args if args else str(message))


@contextlib.contextmanager
def null_timeout(_seconds):
    yield


def make_pipeline(outcomes, *, deep_budget=True, pending_budget=True):
    calls = []
    unavailable = []
    exhausted = []
    logger = Logger()
    iterator = iter(outcomes)

    def generate(model_name, prompt, **kwargs):
        calls.append((model_name, kwargs.get("request_kind"), kwargs.get("request_origin")))
        outcome = next(iterator)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    pipeline = types.SimpleNamespace(
        _generate_via_chat=generate,
        _mark_model_unavailable=lambda model, reason="": unavailable.append((model, reason)),
        _mark_model_exhausted=lambda model, reason="": exhausted.append((model, reason)),
        _extract_retry_delay=lambda exc, default=2: 1,
        _is_gemini_transport_timeout=lambda exc: isinstance(exc, GeminiCallTimeoutError),
        _gemini_call_timeout=null_timeout,
        classify_gemini_quota_error=lambda exc: "UNKNOWN",
        APIError=FakeAPIError,
        GeminiBudgetExceededError=GeminiBudgetExceededError,
        GeminiCallTimeoutError=GeminiCallTimeoutError,
        PendingRetryBudgetExceededError=PendingRetryBudgetExceededError,
        DeepDiveRunBudgetExceededError=DeepDiveRunBudgetExceededError,
        ProductReviewBudgetExceededError=ProductReviewBudgetExceededError,
        NoAvailableModelError=NoAvailableModelError,
        SESSION_EXHAUSTED_MODELS=set(),
        SESSION_UNAVAILABLE_MODELS=set(),
        DEEP_DIVE_MODEL_BUDGET=Budget(deep_budget, used=12 if not deep_budget else 0, budget=12),
        PENDING_RETRY_REQUEST_BUDGET=Budget(pending_budget, used=2 if not pending_budget else 0, budget=2),
        PRODUCT_REVIEW_REQUEST_BUDGET=Budget(True, used=0, budget=3),
        GEMINI_DEEP_DIVE_CALL_PACING_SECONDS=0,
        GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS=120,
        GEMINI_SCREENING_CALL_TIMEOUT_SECONDS=60,
        DEEP_DIVE_MODEL_POOL=["m1", "m2"],
        _PRODUCT_REVIEW_RESPONSE_SCHEMA={},
        _aiif_transient_503_counts={},
        logger=logger,
    )
    resilience.install(pipeline)
    return pipeline, calls, unavailable, exhausted, logger


class ProviderResilienceTests(unittest.TestCase):
    def test_provider_status_uses_structured_fields_only(self):
        self.assertEqual(resilience._provider_status_code(FakeAPIError("x", code=503)), 503)
        response = types.SimpleNamespace(status_code=503)
        self.assertEqual(resilience._provider_status_code(FakeAPIError("x", response=response)), 503)
        self.assertIsNone(resilience._provider_status_code(FakeAPIError("HTTP 503 Service Unavailable")))

    def test_single_503_retries_same_model_and_recovers(self):
        pipeline, calls, unavailable, _, logger = make_pipeline([
            FakeAPIError("provider unavailable", code=503),
            "ok",
        ])
        with mock.patch.object(resilience.time, "sleep", return_value=None):
            response, model = pipeline._call_model_pool("p", None, "deep_dive", 0, ["m1", "m2"], deep_dive=True)
        self.assertEqual((response, model), ("ok", "m1"))
        self.assertEqual([c[0] for c in calls], ["m1", "m1"])
        self.assertEqual(unavailable, [])
        self.assertTrue(any("PROVIDER HTTP 503 RETRY" in row for row in logger.rows))
        self.assertFalse(any("CONFIRMED" in row for row in logger.rows))

    def test_two_consecutive_503s_open_circuit_then_fallback(self):
        pipeline, calls, unavailable, _, logger = make_pipeline([
            FakeAPIError("first", code=503),
            FakeAPIError("second", code=503),
            "fallback-ok",
        ])
        with mock.patch.object(resilience.time, "sleep", return_value=None):
            response, model = pipeline._call_model_pool("p", None, "deep_dive", 0, ["m1", "m2"], deep_dive=True)
        self.assertEqual((response, model), ("fallback-ok", "m2"))
        self.assertEqual([c[0] for c in calls], ["m1", "m1", "m2"])
        self.assertEqual(unavailable, [("m1", "provider_503_confirmed_pair")])
        self.assertTrue(any("PROVIDER HTTP 503 CONFIRMED" in row for row in logger.rows))

    def test_text_only_503_is_not_classified_as_http_503(self):
        pipeline, calls, unavailable, _, logger = make_pipeline([
            FakeAPIError("HTTP 503 Service Unavailable", code=None),
            "fallback-ok",
        ])
        with mock.patch.object(resilience.time, "sleep", return_value=None):
            response, model = pipeline._call_model_pool("p", None, "screening_batch", 0, ["m1", "m2"])
        self.assertEqual((response, model), ("fallback-ok", "m2"))
        self.assertEqual([c[0] for c in calls], ["m1", "m2"])
        self.assertEqual(unavailable, [])
        self.assertFalse(any("PROVIDER HTTP 503" in row for row in logger.rows))

    def test_timeout_after_503_breaks_sequence_without_cooldown(self):
        pipeline, calls, unavailable, _, logger = make_pipeline([
            FakeAPIError("first", code=503),
            GeminiCallTimeoutError("ReadTimeout 503-looking text"),
            "fallback-ok",
        ])
        pipeline._aiif_transient_503_counts["m1"] = 1
        with mock.patch.object(resilience.time, "sleep", return_value=None):
            response, model = pipeline._call_model_pool("p", None, "deep_dive", 0, ["m1", "m2"], deep_dive=True)
        self.assertEqual((response, model), ("fallback-ok", "m2"))
        self.assertEqual(unavailable, [])
        self.assertNotIn("m1", pipeline._aiif_transient_503_counts)
        self.assertTrue(any("distinct_from_http_503=true" in row for row in logger.rows))

    def test_success_clears_legacy_cumulative_503_state(self):
        pipeline, _, _, _, _ = make_pipeline(["ok"])
        pipeline._aiif_transient_503_counts["m1"] = 1
        with mock.patch.object(resilience.time, "sleep", return_value=None):
            pipeline._call_model_pool("p", None, "deep_dive", 0, ["m1"], deep_dive=True)
        self.assertNotIn("m1", pipeline._aiif_transient_503_counts)

    def test_exhausted_deep_dive_budget_is_terminal_before_provider_call(self):
        pipeline, calls, _, _, _ = make_pipeline(["should-not-run"], deep_budget=False)
        with mock.patch.object(resilience.time, "sleep", return_value=None):
            with self.assertRaises(DeepDiveRunBudgetExceededError):
                pipeline._call_model_pool("p", None, "deep_dive", 0, ["m1", "m2"], deep_dive=True)
        self.assertEqual(calls, [])

    def test_exhausted_pending_retry_budget_is_terminal_before_provider_call(self):
        pipeline, calls, _, _, _ = make_pipeline(["should-not-run"], pending_budget=False)
        with mock.patch.object(resilience.time, "sleep", return_value=None):
            with self.assertRaises(PendingRetryBudgetExceededError):
                pipeline._call_model_pool(
                    "p", None, "quality_retry", 0, ["m1", "m2"], deep_dive=True,
                    request_origin="pending_retry",
                )
        self.assertEqual(calls, [])

    def test_product_review_single_503_recovers_on_same_model(self):
        pipeline, calls, unavailable, _, _ = make_pipeline([
            FakeAPIError("provider unavailable", code=503),
            "ok",
        ])
        with mock.patch.object(resilience.time, "sleep", return_value=None):
            response, model = pipeline._call_product_review_pool("prompt", "ctx")
        self.assertEqual((response, model), ("ok", "m1"))
        self.assertEqual([c[0] for c in calls], ["m1", "m1"])
        self.assertEqual(unavailable, [])


if __name__ == "__main__":
    unittest.main()
