"""Offline transport proof for the strict one-turn Deep Dive provider path."""
import unittest
from unittest.mock import patch


class DeepDiveRuntimeTest(unittest.TestCase):
    def test_strict_pool_sends_one_http_attempt_on_503(self):
        import httpx
        from google import genai
        import pipeline as p
        import production_pipeline
        from x_discovery.deep_dive_once import MODEL, REPOSITORY, _strict_single_model_pool

        # Install the same provider/quota wrappers used by the canonical entrypoint.
        production_pipeline.install_runtime_layers(p)
        attempts = []

        def transport(request):
            attempts.append(request)
            return httpx.Response(
                503,
                json={"error": {"code": 503, "message": "offline 503", "status": "UNAVAILABLE"}},
            )

        client = genai.Client(
            api_key="offline-placeholder",
            http_options={
                "client_args": {"transport": httpx.MockTransport(transport), "trust_env": False},
                "async_client_args": {"trust_env": False},
            },
        )
        self.addCleanup(client.close)
        counter = p.PERSISTENT_GEMINI_COUNTER

        with patch.object(p, "client", client), \
             patch.object(p, "GH_PAT", "offline-placeholder"), \
             patch.object(p, "GEMINI_BUDGET", p.GeminiBudget(1, 0, 0)), \
             patch.object(p, "DEEP_DIVE_MODEL_BUDGET", p.DeepDiveModelBudget(1)), \
             patch.object(p, "DEEP_DIVE_MODEL_POOL", [MODEL]), \
             patch.object(p, "send_telegram_alert", lambda *a, **k: None):
            patches = []
            try:
                for name, value in {
                    "enabled": True,
                    "branch": "runtime-state",
                    "repo": REPOSITORY,
                    "counter_scope": "offline",
                }.items():
                    ctx = patch.object(counter, name, value)
                    ctx.start()
                    patches.append(ctx)
                reserve = patch.object(counter, "reserve")
                reserve_mock = reserve.start()
                patches.append(reserve)
                strict_pool = _strict_single_model_pool(p)
                with self.assertRaises(Exception):
                    strict_pool("one offline Deep Dive prompt", request_context="offline-proof")
                self.assertEqual(len(attempts), 1)
                self.assertEqual(p.GEMINI_BUDGET.request_count, 1)
                self.assertEqual(p.DEEP_DIVE_MODEL_BUDGET.used, 1)
                self.assertEqual(reserve_mock.call_count, 1)
            finally:
                for ctx in reversed(patches):
                    ctx.stop()


if __name__ == "__main__":
    unittest.main()
