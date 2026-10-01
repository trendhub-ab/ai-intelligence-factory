from __future__ import annotations

from unittest.mock import patch

import inventory_bootstrap
import pipeline


class FakeAPIError(Exception):
    def __init__(self, code: int):
        super().__init__(f"HTTP {code}")
        self.code = code


def test_product_only_environment_sets_full_product_review_model_pool():
    env = inventory_bootstrap.product_only_environment(2, 3)

    assert env["GEMINI_DEEP_DIVE_MODEL_CANDIDATES"] == (
        "gemini-3.6-flash,gemini-3.7-flash,gemini-3.8-flash,gemini-3.5-flash"
    )


def test_product_review_503_falls_through_to_next_distinct_model_without_same_model_retry():
    calls: list[str] = []

    def generate(model_name, *args, **kwargs):
        calls.append(model_name)
        if model_name == "gemini-3.6-flash":
            raise FakeAPIError(503)
        return {"ok": True}

    with patch.object(pipeline, "APIError", FakeAPIError), \
         patch.object(
             pipeline,
             "DEEP_DIVE_MODEL_POOL",
             ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.5-flash"],
         ), \
         patch.object(pipeline, "SESSION_EXHAUSTED_MODELS", set()), \
         patch.object(pipeline, "SESSION_UNAVAILABLE_MODELS", set()), \
         patch.object(pipeline.PRODUCT_REVIEW_REQUEST_BUDGET, "can_request", return_value=True), \
         patch.object(pipeline, "_generate_via_chat", side_effect=generate), \
         patch.object(pipeline, "_mark_model_unavailable") as mark_unavailable:
        response, model = pipeline._call_product_review_pool("prompt", "ctx")

    assert response == {"ok": True}
    assert model == "gemini-3.7-flash"
    assert calls == ["gemini-3.6-flash", "gemini-3.7-flash"]
    mark_unavailable.assert_any_call(
        "gemini-3.6-flash", "provider_503_product_review_fallback_preserved"
    )


def test_product_review_three_503s_spend_three_requests_across_three_distinct_models():
    calls: list[str] = []

    def generate(model_name, *args, **kwargs):
        calls.append(model_name)
        raise FakeAPIError(503)

    budget_answers = [True, True, True, False]

    with patch.object(pipeline, "APIError", FakeAPIError), \
         patch.object(
             pipeline,
             "DEEP_DIVE_MODEL_POOL",
             ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.5-flash"],
         ), \
         patch.object(pipeline, "SESSION_EXHAUSTED_MODELS", set()), \
         patch.object(pipeline, "SESSION_UNAVAILABLE_MODELS", set()), \
         patch.object(
             pipeline.PRODUCT_REVIEW_REQUEST_BUDGET,
             "can_request",
             side_effect=budget_answers,
         ), \
         patch.object(pipeline, "_generate_via_chat", side_effect=generate), \
         patch.object(pipeline, "_mark_model_unavailable"):
        try:
            pipeline._call_product_review_pool("prompt", "ctx")
        except pipeline.ProductReviewBudgetExceededError:
            pass
        else:
            raise AssertionError("expected ProductReviewBudgetExceededError")

    assert calls == [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
    ]
