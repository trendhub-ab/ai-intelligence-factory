"""Run360 regression: Gemini transport retry has exactly one owner."""
from __future__ import annotations

import logging
import types
import unittest

import gemini_provider_resilience as resilience


class _FakeClient:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        type(self).calls.append(dict(kwargs))
        self.kwargs = dict(kwargs)


class _FakeAPIError(Exception):
    pass


def _pipeline(api_key: str = "test-key"):
    return types.SimpleNamespace(
        GEMINI_API_KEY=api_key,
        genai=types.SimpleNamespace(Client=_FakeClient),
        client=object(),
        APIError=_FakeAPIError,
        _generate_via_chat=lambda *args, **kwargs: None,
        _mark_model_unavailable=lambda *args, **kwargs: None,
        _mark_model_exhausted=lambda *args, **kwargs: None,
        _extract_retry_delay=lambda exc, default: default,
        _is_gemini_transport_timeout=lambda exc: False,
        logger=logging.getLogger("run360-test"),
    )


class Run360GeminiRetryOwnerTest(unittest.TestCase):
    def setUp(self):
        _FakeClient.calls.clear()

    def test_install_rebuilds_client_with_one_total_sdk_attempt(self):
        pipeline = _pipeline()

        resilience.install(pipeline)

        self.assertEqual(len(_FakeClient.calls), 1)
        self.assertEqual(_FakeClient.calls[0]["api_key"], "test-key")
        self.assertEqual(
            _FakeClient.calls[0]["http_options"],
            {"retry_options": {"attempts": 1}},
        )
        self.assertIsInstance(pipeline.client, _FakeClient)
        self.assertEqual(pipeline.GEMINI_SDK_RETRY_ATTEMPTS, 1)
        self.assertEqual(pipeline.GEMINI_RETRY_OWNER, "factory")
        self.assertTrue(pipeline._aiif_gemini_sdk_single_retry_owner_installed)

    def test_install_is_idempotent_and_does_not_stack_clients(self):
        pipeline = _pipeline()

        resilience.install(pipeline)
        first_client = pipeline.client
        resilience.install(pipeline)

        self.assertEqual(len(_FakeClient.calls), 1)
        self.assertIs(pipeline.client, first_client)

    def test_no_key_offline_import_does_not_construct_provider_client(self):
        pipeline = _pipeline(api_key="")

        resilience.install(pipeline)

        self.assertEqual(_FakeClient.calls, [])
        self.assertEqual(pipeline.GEMINI_SDK_RETRY_ATTEMPTS, 1)
        self.assertEqual(pipeline.GEMINI_RETRY_OWNER, "factory")


if __name__ == "__main__":
    unittest.main()
