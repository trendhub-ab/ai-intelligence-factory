#!/usr/bin/env python3
"""One-time source patch for provider-aligned Gemini persistent counting.

This script is intentionally deterministic and idempotent. It never calls Gemini.
It patches pipeline.py so all Gemini models share the same accounting rule:
- reserve before send (concurrency / fail-closed safety),
- keep the reservation on success and provider-visible HTTP/API errors,
- release only transport/watchdog timeouts for which no provider response was observed.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline.py"
TEST_FILE = ROOT / "tests" / "test_gemini_counter_reconciliation.py"
MARKER = "[GEMINI PERSISTENT RECONCILE]"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_pipeline() -> bool:
    text = PIPELINE.read_text(encoding="utf-8")
    if MARKER in text and "def release_unobserved(" in text:
        return False

    old_catch = '''    except Exception as exc:\n        GEMINI_USAGE_AUDIT.record_outcome(audit_id, "error", exc)\n        raise\n'''
    new_catch = '''    except Exception as exc:\n        GEMINI_USAGE_AUDIT.record_outcome(audit_id, "error", exc)\n        # Persistent RPD state is reserved before send to remain concurrency-safe.\n        # Provider-visible API/HTTP errors (429/503 etc.) stay counted because the\n        # provider may charge/count those attempts. Only transport/watchdog timeout\n        # families without a usable provider response are released. This rule is\n        # model-agnostic and therefore applies to Flash / Flash-Lite and future models.\n        if _is_gemini_transport_timeout(exc):\n            try:\n                PERSISTENT_GEMINI_COUNTER.release_unobserved(request_kind, model_name=model_name)\n                logger.warning(\n                    f"{MARKER} released unobserved timeout reservation "\n                    f"model={model_name} kind={request_kind} error={exc.__class__.__name__}"\n                )\n            except Exception as reconcile_exc:\n                # Reconciliation must never convert a provider timeout into a pipeline\n                # outage. Keeping the reservation is the safe failure mode.\n                logger.warning(\n                    f"{MARKER} release failed; reservation kept fail-closed "\n                    f"model={model_name} kind={request_kind} error={reconcile_exc}"\n                )\n        raise\n'''
    text = replace_once(text, old_catch, new_catch, "generate_via_chat catch")

    old_write_sig = '''    def _write_remote(self, data: dict, sha: str | None) -> None:\n'''
    new_write_sig = '''    def _write_remote(self, data: dict, sha: str | None, action: str = "reserve") -> None:\n'''
    text = replace_once(text, old_write_sig, new_write_sig, "write_remote signature")

    old_message = '''            "message": f"chore: reserve Gemini request {data.get('quota_date','')} ({self.counter_scope})",\n'''
    new_message = '''            "message": f"chore: {action} Gemini request {data.get('quota_date','')} ({self.counter_scope})",\n'''
    text = replace_once(text, old_message, new_message, "counter commit message")

    old_tail = '''        raise GeminiBudgetExceededError("Persistent Gemini counter reservation failed after retries")\n\n    def summary(self) -> str:\n'''
    new_tail = '''        raise GeminiBudgetExceededError("Persistent Gemini counter reservation failed after retries")\n\n    def release_unobserved(self, kind: str, model_name: str = "default") -> None:\n        """Release one pre-send reservation after a transport/watchdog timeout.\n\n        This method is deliberately *not* used for provider-visible API/HTTP errors\n        such as 429/503. The provider dashboard can count those attempts, so keeping\n        them reserved is the fail-closed truth. Release is restricted to timeout\n        families classified by ``_is_gemini_transport_timeout`` at the call site.\n\n        ``session_used`` and the per-run budgets remain attempt counters and are not\n        decremented; only the cross-run persistent RPD safety estimate is reconciled.\n        """\n        if not self.enabled:\n            return\n        if not self.counter_scope:\n            raise GeminiBudgetExceededError("Persistent Gemini counter has no stable scope")\n        quota_date = self._quota_date()\n        budget = self.budget_for(model_name)\n        for attempt in range(3):\n            data, sha = self._read_remote()\n            data = self._normalized_day(data, quota_date)\n            state = self._model_state(data, model_name)\n            used = int(state.get("used", 0) or 0)\n            by_kind = state.get("by_kind") if isinstance(state.get("by_kind"), dict) else {}\n            kind_used = int(by_kind.get(kind, 0) or 0)\n\n            # Never manufacture quota. If the matching reservation cannot be proven,\n            # retain the existing count rather than risk under-counting provider usage.\n            if used <= 0 or kind_used <= 0:\n                logger.warning(\n                    f"{MARKER} no matching reservation; kept fail-closed "\n                    f"model={model_name} kind={kind} used={used} kind_used={kind_used}"\n                )\n                return\n\n            state["used"] = used - 1\n            state["budget"] = budget\n            state["exhausted"] = state["used"] >= budget\n            by_kind[kind] = kind_used - 1\n            if by_kind[kind] <= 0:\n                by_kind.pop(kind, None)\n            state["by_kind"] = by_kind\n            state["released_unobserved"] = int(state.get("released_unobserved", 0) or 0) + 1\n            released_by_kind = (\n                state.get("released_by_kind")\n                if isinstance(state.get("released_by_kind"), dict)\n                else {}\n            )\n            released_by_kind[kind] = int(released_by_kind.get(kind, 0) or 0) + 1\n            state["released_by_kind"] = released_by_kind\n            data["updated_at"] = datetime.now(timezone.utc).isoformat()\n            data["scope_kind"] = "repository_local"\n            if self.provider_project_scope:\n                data["provider_project_fingerprint"] = self.provider_project_scope\n            try:\n                self._write_remote(data, sha, action="release-unobserved")\n                return\n            except GeminiBudgetExceededError as e:\n                msg = str(e)\n                if attempt < 2 and ("HTTP 409" in msg or "HTTP 422" in msg):\n                    time.sleep(0.5 * (attempt + 1))\n                    continue\n                raise\n\n        raise GeminiBudgetExceededError("Persistent Gemini counter release failed after retries")\n\n    def summary(self) -> str:\n'''
    text = replace_once(text, old_tail, new_tail, "persistent counter release method")

    PIPELINE.write_text(text, encoding="utf-8")
    return True


TEST_CONTENT = r'''import copy
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
'''


def ensure_test() -> bool:
    if TEST_FILE.exists() and TEST_FILE.read_text(encoding="utf-8") == TEST_CONTENT:
        return False
    TEST_FILE.write_text(TEST_CONTENT, encoding="utf-8")
    return True


def main() -> int:
    changed_pipeline = patch_pipeline()
    changed_test = ensure_test()
    print({"pipeline_changed": changed_pipeline, "test_changed": changed_test, "zero_gemini_calls": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
