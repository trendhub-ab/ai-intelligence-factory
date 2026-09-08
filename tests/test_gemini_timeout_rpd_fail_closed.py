from __future__ import annotations

import logging
import types
import unittest

import gemini_timeout_rpd_fail_closed as guard


class Counter:
    def __init__(self):
        self.release_calls = []

    def release_unobserved(self, kind, model_name="default"):
        self.release_calls.append((kind, model_name))


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class TimeoutFailClosedTests(unittest.TestCase):
    def test_release_is_suppressed_and_legacy_log_is_rewritten(self):
        counter = Counter()
        logger = logging.getLogger("run303-timeout-test")
        logger.handlers.clear()
        logger.filters.clear()
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        capture = Capture()
        logger.addHandler(capture)
        pipeline = types.SimpleNamespace(PERSISTENT_GEMINI_COUNTER=counter, logger=logger)

        guard.install(pipeline)
        counter.release_unobserved("deep_dive", model_name="gemini-x")
        logger.warning(
            "[GEMINI PERSISTENT RECONCILE] released unobserved timeout reservation "
            "model=gemini-x kind=deep_dive error=ReadTimeout"
        )

        self.assertEqual(counter.release_calls, [])
        self.assertTrue(any("GEMINI RPD FAIL-CLOSED" in message for message in capture.messages))
        self.assertTrue(any("release suppressed by Run209; timeout reservation kept" in message for message in capture.messages))
        self.assertFalse(any("released unobserved timeout reservation" in message for message in capture.messages))

    def test_install_is_idempotent(self):
        counter = Counter()
        logger = logging.getLogger("run303-timeout-test-idempotent")
        logger.handlers.clear()
        logger.filters.clear()
        pipeline = types.SimpleNamespace(PERSISTENT_GEMINI_COUNTER=counter, logger=logger)
        guard.install(pipeline)
        first_release = counter.release_unobserved
        first_filters = len(logger.filters)
        guard.install(pipeline)
        self.assertIs(counter.release_unobserved, first_release)
        self.assertEqual(len(logger.filters), first_filters)
