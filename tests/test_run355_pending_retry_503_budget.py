from __future__ import annotations

import contextlib
import types
import unittest
from unittest import mock

import gemini_provider_resilience as resilience


class FakeAPIError(Exception):
    def __init__(self, message: str, code=None):
        super().__init__(message)
        self.code = code
        self.response = None


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
    def __init__(self, budget: int):
        self.budget = budget
        self.used = 0

    def can_request(self):
        return self.used < self.budget


@contextlib.contextmanager
def null_timeout(_seconds):
    yield


class Run355PendingRetry503BudgetTests(unittest.TestCase):
    def test_pending_retry_first_503_falls_back_without_same_model_confirmation(self):
        calls = []
        unavailable = []
        outcomes = iter([FakeAPIError("provider unavailable", code=503), "fallback-ok"])
        pending_budget = Budget(2)
        deep_budget = Budget(12)

        def generate(model_name, prompt, **kwargs):
            calls.append(model_name)
            pending_budget.used += 1
            deep_budget.used += 1
            outcome = next(outcomes)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        pipeline = types.SimpleNamespace(
            _generate_via_chat=generate,
            _mark_model_unavailable=lambda model, reason="": unavailable.append((model, reason)),
            _mark_model_exhausted=lambda *_args, **_kwargs: None,
            _extract_retry_delay=lambda *_args, **_kwargs: 1,
            _is_gemini_transport_timeout=lambda exc: isinstance(exc, GeminiCallTimeoutError),
            _gemini_call_timeout=null_timeout,
            classify_gemini_quota_error=lambda _exc: "UNKNOWN",
            APIError=FakeAPIError,
            GeminiBudgetExceededError=GeminiBudgetExceededError,
            GeminiCallTimeoutError=GeminiCallTimeoutError,
            PendingRetryBudgetExceededError=PendingRetryBudgetExceededError,
            DeepDiveRunBudgetExceededError=DeepDiveRunBudgetExceededError,
            ProductReviewBudgetExceededError=ProductReviewBudgetExceededError,
            NoAvailableModelError=NoAvailableModelError,
            SESSION_EXHAUSTED_MODELS=set(),
            SESSION_UNAVAILABLE_MODELS=set(),
            DEEP_DIVE_MODEL_BUDGET=deep_budget,
            PENDING_RETRY_REQUEST_BUDGET=pending_budget,
            GEMINI_DEEP_DIVE_CALL_PACING_SECONDS=0,
            GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS=120,
            GEMINI_SCREENING_CALL_TIMEOUT_SECONDS=60,
            _aiif_transient_503_counts={},
            logger=types.SimpleNamespace(warning=lambda *_args, **_kwargs: None),
        )
        resilience.install(pipeline)

        with mock.patch.object(resilience.time, "sleep", return_value=None):
            response, model = pipeline._call_model_pool(
                "p", None, "quality_retry", 0, ["m1", "m2"], deep_dive=True,
                request_origin="pending_retry",
            )

        self.assertEqual((response, model), ("fallback-ok", "m2"))
        self.assertEqual(calls, ["m1", "m2"])
        self.assertEqual(pending_budget.used, 2)
        self.assertEqual(unavailable, [("m1", "provider_503_pending_retry_budget_preserved")])


if __name__ == "__main__":
    unittest.main()
