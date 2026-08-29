import unittest
from unittest.mock import patch

import pipeline


class FakeHttpxReadTimeout(Exception):
    pass


FakeHttpxReadTimeout.__module__ = "httpx"


class TestGeminiTransportTimeoutFallback(unittest.TestCase):
    def setUp(self):
        pipeline.SESSION_EXHAUSTED_MODELS.clear()
        pipeline.SESSION_UNAVAILABLE_MODELS.clear()

    def test_httpx_timeout_is_recognized_but_runtime_error_is_not(self):
        self.assertTrue(pipeline._is_gemini_transport_timeout(FakeHttpxReadTimeout("slow")))
        self.assertTrue(pipeline._is_gemini_transport_timeout(pipeline.GeminiCallTimeoutError("watchdog")))
        self.assertFalse(pipeline._is_gemini_transport_timeout(RuntimeError("bug")))

    def test_screening_timeout_falls_back_to_next_model(self):
        sentinel = object()
        with patch.object(
            pipeline,
            "_generate_via_chat",
            side_effect=[FakeHttpxReadTimeout("Gemini call exceeded 60s"), sentinel],
        ) as generate:
            response, model = pipeline._call_model_pool(
                "prompt", None, "screening_batch", 0, ["primary-lite", "fallback-lite"],
                deep_dive=False, request_context="test-timeout",
            )
        self.assertIs(response, sentinel)
        self.assertEqual(model, "fallback-lite")
        self.assertEqual(generate.call_count, 2)

    def test_unrelated_exception_still_fails_loudly(self):
        with patch.object(pipeline, "_generate_via_chat", side_effect=RuntimeError("programming bug")):
            with self.assertRaisesRegex(RuntimeError, "programming bug"):
                pipeline._call_model_pool(
                    "prompt", None, "screening_batch", 0, ["primary-lite", "fallback-lite"],
                    deep_dive=False, request_context="test-non-timeout",
                )


if __name__ == "__main__":
    unittest.main()
