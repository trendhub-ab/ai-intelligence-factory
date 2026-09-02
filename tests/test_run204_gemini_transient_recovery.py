import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import gemini_transient_recovery as recovery


class Run204GeminiTransientRecoveryTests(unittest.TestCase):
    def _pipeline(self):
        unavailable = set()
        logger = Mock()

        def original(model_name, reason=""):
            unavailable.add(model_name)

        return SimpleNamespace(
            SESSION_UNAVAILABLE_MODELS=unavailable,
            _mark_model_unavailable=original,
            logger=logger,
        )

    def test_503_is_not_session_blacklisted(self):
        pipeline = self._pipeline()
        recovery.install(pipeline)

        pipeline._mark_model_unavailable("gemini-3.6-flash", "503")

        self.assertNotIn("gemini-3.6-flash", pipeline.SESSION_UNAVAILABLE_MODELS)
        self.assertEqual(pipeline._aiif_transient_503_counts["gemini-3.6-flash"], 1)
        pipeline.logger.warning.assert_called_once()

    def test_repeated_503_remains_bounded_recoverable_not_hard_unavailable(self):
        pipeline = self._pipeline()
        recovery.install(pipeline)

        pipeline._mark_model_unavailable("gemini-3.7-flash", "503")
        pipeline._mark_model_unavailable("gemini-3.7-flash", "503 Service Unavailable")

        self.assertNotIn("gemini-3.7-flash", pipeline.SESSION_UNAVAILABLE_MODELS)
        self.assertEqual(pipeline._aiif_transient_503_counts["gemini-3.7-flash"], 2)

    def test_404_stays_hard_unavailable(self):
        pipeline = self._pipeline()
        recovery.install(pipeline)

        pipeline._mark_model_unavailable("retired-model", "404")

        self.assertIn("retired-model", pipeline.SESSION_UNAVAILABLE_MODELS)

    def test_timeout_circuit_breaker_stays_hard_unavailable(self):
        pipeline = self._pipeline()
        recovery.install(pipeline)

        pipeline._mark_model_unavailable(
            "gemini-3.5-flash", "transport_timeout_circuit_breaker:2"
        )

        self.assertIn("gemini-3.5-flash", pipeline.SESSION_UNAVAILABLE_MODELS)

    def test_install_is_idempotent(self):
        pipeline = self._pipeline()
        recovery.install(pipeline)
        first_marker = pipeline._mark_model_unavailable
        recovery.install(pipeline)

        self.assertIs(first_marker, pipeline._mark_model_unavailable)
        pipeline._mark_model_unavailable("gemini-3.6-flash", "503")
        self.assertEqual(pipeline._aiif_transient_503_counts["gemini-3.6-flash"], 1)


if __name__ == "__main__":
    unittest.main()
