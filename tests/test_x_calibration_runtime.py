"""Offline transport proof through the installed production entrypoint."""
import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch


class RuntimeTest(unittest.TestCase):
    def test_installed_entrypoint_sends_one_http_attempt_on_503(self):
        import httpx
        from google import genai
        import pipeline as p
        import production_pipeline
        from x_discovery.calibration_once import OPERATION, REPOSITORY
        attempts = []
        def transport(request):
            attempts.append(request)
            return httpx.Response(503, json={"error": {"code": 503, "message": "offline 503", "status": "UNAVAILABLE"}})
        client = genai.Client(api_key="offline-placeholder", http_options={
            "client_args": {"transport": httpx.MockTransport(transport), "trust_env": False},
            "async_client_args": {"trust_env": False}})
        self.addCleanup(client.close)
        env = {
            "AIIF_ONE_SHOT_MODE": "x_saved_candidate_calibration_validation",
            "AIIF_X_CALIBRATION_EXECUTE": "true",
            "AIIF_X_CALIBRATION_OPERATION": OPERATION,
            "GITHUB_RUN_ATTEMPT": "1",
            "AIIF_X_SAVED_CANDIDATE_PATH": "x_discovery/fixtures/defense_factory_boundary_20260911.json",
            "AIIF_X_SAVED_SCREENING_PATH": "x_discovery/fixtures/defense_factory_screening_result_20260911.json",
        }
        counter = p.PERSISTENT_GEMINI_COUNTER
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, env))
            stack.enter_context(patch.object(p, "client", client))
            stack.enter_context(patch.object(p, "GH_PAT", "offline-placeholder"))
            stack.enter_context(patch.object(p, "SCREENING_MODEL_POOL", ["gemini-3.5-flash-lite"]))
            stack.enter_context(patch.object(p, "GEMINI_BUDGET", p.GeminiBudget(1, 0, 0)))
            stack.enter_context(patch.object(p, "send_telegram_alert", lambda *a, **k: None))
            for name, value in {"enabled": True, "branch": "runtime-state", "repo": REPOSITORY,
                                "counter_scope": "offline"}.items():
                stack.enter_context(patch.object(counter, name, value))
            reserve = stack.enter_context(patch.object(counter, "reserve"))
            claim = stack.enter_context(patch("x_discovery.calibration_once.claim_operation"))
            stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")))
            stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("network forbidden")))
            with self.assertRaises(Exception):
                production_pipeline.main()
            self.assertEqual(len(attempts), 1)
            self.assertEqual(p.GEMINI_BUDGET.request_count, 1)
            self.assertEqual(claim.call_count, 1)
            self.assertEqual(reserve.call_count, 1)
