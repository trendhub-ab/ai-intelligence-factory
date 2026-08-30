import copy
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SYNTHETIC_REGRESSION_MODE", "true")

import pipeline


class FakeReadTimeout(Exception):
    pass


FakeReadTimeout.__module__ = "httpx"


class FakeServerError(Exception):
    pass


FakeServerError.__module__ = "google.genai.errors"


class _FakeChat:
    def __init__(self, exc):
        self.exc = exc

    def send_message(self, prompt):
        raise self.exc


class _FakeClient:
    def __init__(self, exc):
        self.exc = exc
        self.chats = self

    def create(self, **kwargs):
        return _FakeChat(self.exc)


class _FakePersistent:
    def __init__(self):
        self.released = []

    def release_unobserved(self, kind, model_name="default"):
        self.released.append((kind, model_name))


class GeminiCounterReconciliationTests(unittest.TestCase):
    MODELS = (
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
    )

    def _counter(self, model):
        counter = pipeline.PersistentGeminiDailyCounter(
            True,
            {model: 18},
            18,
            path=".runtime/test.json",
            quota_timezone="America/Los_Angeles",
            quota_scope_id="unit-test-scope",
        )
        scope = counter.counter_scope
        remote = {
            "schema_version": 3,
            "quota_date": counter._quota_date(),
            "counter_scopes": {
                scope: {
                    "models": {
                        model: {
                            "used": 2,
                            "budget": 18,
                            "by_kind": {"quality_retry": 2},
                            "exhausted": False,
                        }
                    }
                }
            },
        }
        writes = []

        def read_remote():
            return copy.deepcopy(remote), "sha"

        def write_remote(data, sha, action="reserve"):
            remote.clear()
            remote.update(copy.deepcopy(data))
            writes.append((copy.deepcopy(data), action))

        counter._read_remote = read_remote
        counter._write_remote = write_remote
        return counter, remote, writes

    def test_transport_timeout_classifier_is_model_independent(self):
        self.assertTrue(pipeline._is_gemini_transport_timeout(FakeReadTimeout("timeout")))
        self.assertTrue(pipeline._is_gemini_transport_timeout(pipeline.GeminiCallTimeoutError("timeout")))
        self.assertFalse(pipeline._is_gemini_transport_timeout(FakeServerError("503")))
        self.assertFalse(pipeline._is_gemini_transport_timeout(RuntimeError("unknown")))

    def test_release_unobserved_decrements_all_models_equally(self):
        for model in self.MODELS:
            with self.subTest(model=model):
                counter, remote, writes = self._counter(model)
                counter.release_unobserved("quality_retry", model_name=model)
                state = remote["counter_scopes"][counter.counter_scope]["models"][model]
                self.assertEqual(state["used"], 1)
                self.assertEqual(state["by_kind"]["quality_retry"], 1)
                self.assertEqual(state["released_unobserved"], 1)
                self.assertEqual(state["released_by_kind"]["quality_retry"], 1)
                self.assertEqual(writes[-1][1], "release-unobserved")

    def test_release_clears_exhausted_and_never_underflows(self):
        model = "gemini-3.6-flash"
        counter, remote, writes = self._counter(model)
        state = remote["counter_scopes"][counter.counter_scope]["models"][model]
        state["used"] = 18
        state["by_kind"]["quality_retry"] = 1
        state["exhausted"] = True
        counter.release_unobserved("quality_retry", model_name=model)
        state = remote["counter_scopes"][counter.counter_scope]["models"][model]
        self.assertEqual(state["used"], 17)
        self.assertFalse(state["exhausted"])

        state["used"] = 0
        state["by_kind"] = {}
        before = len(writes)
        counter.release_unobserved("quality_retry", model_name=model)
        self.assertEqual(len(writes), before)
        self.assertEqual(state["used"], 0)

    def test_generate_via_chat_releases_read_timeout_for_every_model(self):
        for model in self.MODELS:
            with self.subTest(model=model):
                persistent = _FakePersistent()
                with patch.object(pipeline, "client", _FakeClient(FakeReadTimeout("timeout"))), \
                     patch.object(pipeline, "PERSISTENT_GEMINI_COUNTER", persistent), \
                     patch.object(pipeline, "_consume_gemini_request", return_value=0), \
                     patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_outcome"):
                    with self.assertRaises(FakeReadTimeout):
                        pipeline._generate_via_chat(model, "prompt", request_kind="quality_retry")
                self.assertEqual(persistent.released, [("quality_retry", model)])

    def test_generate_via_chat_keeps_provider_server_errors_fail_closed(self):
        for model in self.MODELS:
            with self.subTest(model=model):
                persistent = _FakePersistent()
                with patch.object(pipeline, "client", _FakeClient(FakeServerError("503"))), \
                     patch.object(pipeline, "PERSISTENT_GEMINI_COUNTER", persistent), \
                     patch.object(pipeline, "_consume_gemini_request", return_value=0), \
                     patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_outcome"):
                    with self.assertRaises(FakeServerError):
                        pipeline._generate_via_chat(model, "prompt", request_kind="deep_dive_retry")
                self.assertEqual(persistent.released, [])

    def test_unknown_errors_remain_counted_fail_closed(self):
        persistent = _FakePersistent()
        with patch.object(pipeline, "client", _FakeClient(RuntimeError("unknown"))), \
             patch.object(pipeline, "PERSISTENT_GEMINI_COUNTER", persistent), \
             patch.object(pipeline, "_consume_gemini_request", return_value=0), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_outcome"):
            with self.assertRaises(RuntimeError):
                pipeline._generate_via_chat("gemini-3.6-flash", "prompt", request_kind="deep_dive")
        self.assertEqual(persistent.released, [])


if __name__ == "__main__":
    unittest.main()
