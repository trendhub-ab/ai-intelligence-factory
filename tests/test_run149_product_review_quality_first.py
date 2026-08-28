import inspect
import unittest
from unittest.mock import MagicMock, patch

import pipeline


class Run149ProductReviewQualityFirstTests(unittest.TestCase):
    def _capture_config(self, request_kind_base):
        budget = MagicMock()
        budget.can_request.return_value = True
        budget.summary.return_value = "ok"
        with patch.object(pipeline, "PRODUCT_REVIEW_REQUEST_BUDGET", budget), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["gemini-3.6-flash"]), \
             patch.object(pipeline, "SESSION_EXHAUSTED_MODELS", set()), \
             patch.object(pipeline, "SESSION_UNAVAILABLE_MODELS", set()), \
             patch.object(pipeline, "GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", 0), \
             patch.object(pipeline, "_generate_via_chat", return_value=object()) as generate:
            pipeline._call_product_review_pool(
                "prompt", "context", request_kind_base=request_kind_base
            )
        return generate.call_args.kwargs["config"]

    def test_primary_review_preserves_medium_thinking_quality(self):
        config = self._capture_config("product_review")
        self.assertEqual(config["thinking_config"], {"thinking_level": "medium"})
        self.assertEqual(config["max_output_tokens"], 8000)

    def test_structured_retry_uses_low_thinking_recovery_profile(self):
        config = self._capture_config("product_review_retry")
        self.assertEqual(config["thinking_config"], {"thinking_level": "low"})
        self.assertEqual(config["max_output_tokens"], 5000)

    def test_profile_depends_on_logical_request_not_transport_attempt(self):
        source = inspect.getsource(pipeline._call_product_review_pool)
        self.assertIn('structured_repair = request_kind_base == "product_review_retry"', source)
        self.assertIn('thinking_level = "low" if structured_repair else "medium"', source)
        self.assertIn('max_output_tokens = 5000 if structured_repair else 8000', source)


if __name__ == "__main__":
    unittest.main()
