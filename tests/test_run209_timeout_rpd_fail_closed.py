import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SYNTHETIC_REGRESSION_MODE", "true")

import gemini_timeout_rpd_fail_closed as run209
import pipeline


ROOT = Path(__file__).resolve().parents[1]


class FakeReadTimeout(Exception):
    pass


FakeReadTimeout.__module__ = "httpx"


class _FakeChat:
    def send_message(self, prompt):
        raise FakeReadTimeout("provider response not observed")


class _FakeClient:
    def __init__(self):
        self.chats = self

    def create(self, **kwargs):
        return _FakeChat()


class _FakeCounter:
    def __init__(self):
        self.original_release_calls = []

    def release_unobserved(self, kind, model_name="default"):
        self.original_release_calls.append((kind, model_name))


class _FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args):
        self.warnings.append(message % args if args else message)


class Run209TimeoutRpdFailClosedTests(unittest.TestCase):
    def test_install_keeps_timeout_reservation_and_preserves_original_for_diagnostics(self):
        counter = _FakeCounter()
        logger = _FakeLogger()
        module = SimpleNamespace(PERSISTENT_GEMINI_COUNTER=counter, logger=logger)

        run209.install(module)
        counter.release_unobserved("quality_retry", model_name="gemini-3.7-flash")

        self.assertEqual(counter.original_release_calls, [])
        self.assertTrue(counter._run209_timeout_rpd_fail_closed_installed)
        self.assertTrue(module.RUN209_TIMEOUT_RPD_FAIL_CLOSED)
        self.assertTrue(callable(counter._run209_original_release_unobserved))
        self.assertTrue(any("timeout reservation kept" in line for line in logger.warnings))

    def test_install_is_idempotent(self):
        counter = _FakeCounter()
        module = SimpleNamespace(PERSISTENT_GEMINI_COUNTER=counter, logger=_FakeLogger())

        run209.install(module)
        first_wrapper = counter.release_unobserved
        first_original = counter._run209_original_release_unobserved
        run209.install(module)

        self.assertIs(counter.release_unobserved, first_wrapper)
        self.assertIs(counter._run209_original_release_unobserved, first_original)

    def test_missing_counter_fails_closed(self):
        with self.assertRaises(RuntimeError):
            run209.install(SimpleNamespace(logger=_FakeLogger()))

    def test_real_chat_timeout_no_longer_rolls_back_reserved_rpd(self):
        counter = _FakeCounter()
        with patch.object(pipeline, "PERSISTENT_GEMINI_COUNTER", counter), \
             patch.object(pipeline, "client", _FakeClient()), \
             patch.object(pipeline, "_consume_gemini_request", return_value=101), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_outcome"), \
             patch.object(pipeline.GEMINI_USAGE_AUDIT, "record_response_usage"):
            run209.install(pipeline)
            with self.assertRaises(FakeReadTimeout):
                pipeline._generate_via_chat(
                    "gemini-3.7-flash",
                    "prompt",
                    request_kind="quality_retry",
                )

        self.assertEqual(counter.original_release_calls, [])

    def test_production_installs_run209_after_runtime_state_channel(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        runtime_pos = source.index("runtime_state_channel.install(pipeline_module)")
        run209_pos = source.index("gemini_timeout_rpd_fail_closed.install(pipeline_module)")
        transient_pos = source.index("gemini_transient_recovery.install(pipeline_module)")
        self.assertLess(runtime_pos, run209_pos)
        self.assertLess(run209_pos, transient_pos)

    def test_flash_daily_safety_ceiling_remains_18_not_provider_limit_20(self):
        one_shot = (ROOT / ".github" / "workflows" / "daily-one-shot.yml").read_text(encoding="utf-8")
        daily = (ROOT / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
        for workflow in (one_shot, daily):
            self.assertIn('GEMINI_36_FLASH_DAILY_BUDGET: "18"', workflow)
            self.assertIn('GEMINI_37_FLASH_DAILY_BUDGET: "18"', workflow)
            self.assertIn('GEMINI_35_FLASH_DAILY_BUDGET: "18"', workflow)
            self.assertNotIn('GEMINI_36_FLASH_DAILY_BUDGET: "20"', workflow)
            self.assertNotIn('GEMINI_37_FLASH_DAILY_BUDGET: "20"', workflow)
            self.assertNotIn('GEMINI_35_FLASH_DAILY_BUDGET: "20"', workflow)


if __name__ == "__main__":
    unittest.main()
