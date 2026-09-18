from __future__ import annotations

import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import run260_gemini_model_routing as run260


class Run370ProviderHealthPersistenceTests(unittest.TestCase):
    def test_append_deduplicates_nested_capture_and_strips_context(self):
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "gemini-3.7-flash",
            "kind": "deep_dive",
            "context": "private candidate context",
            "outcome": "success",
            "error_type": "",
        }
        p = types.SimpleNamespace(_provider_health_history=[])
        with patch.object(run260, "_persist_provider_health_history") as persist:
            self.assertTrue(run260._append_health_rows(p, [row]))
            self.assertFalse(run260._append_health_rows(p, [row]))
        self.assertEqual(len(p._provider_health_history), 1)
        self.assertNotIn("context", p._provider_health_history[0])
        persist.assert_called_once_with(p)

    def test_provider_health_prefers_runtime_state_actions_token(self):
        p = types.SimpleNamespace(requests=object())
        env = {
            "GITHUB_REPOSITORY": "trendhub-ab/ai-intelligence-factory",
            "GH_PAT": "operator-rate-limited-token",
            "AIIF_RUNTIME_STATE_GITHUB_TOKEN": "actions-runtime-token",
            "AIIF_RUNTIME_STATE_BRANCH": "runtime-state",
        }
        with patch.dict("os.environ", env, clear=True):
            location = run260._health_state_location(p)
        self.assertIsNotNone(location)
        self.assertEqual(location[1], "actions-runtime-token")
        self.assertEqual(location[2], "runtime-state")

    def test_actual_usage_audit_shape_is_accepted(self):
        p = types.SimpleNamespace(
            GEMINI_USAGE_AUDIT=types.SimpleNamespace(records=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "gemini-3.6-flash",
                "kind": "quality_retry",
                "context": "short internal context",
                "outcome": "error",
                "error_type": "APIError",
                "prompt_tokens": 123,
                "output_tokens": 0,
                "total_tokens": 123,
            }])
        )
        rows = run260._new_audit_rows(p, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model"], "gemini-3.6-flash")
        self.assertEqual(rows[0]["outcome"], "error")
        self.assertEqual(rows[0]["error_type"], "APIError")
        self.assertNotIn("context", rows[0])
        self.assertNotIn("prompt_tokens", rows[0])


if __name__ == "__main__":
    unittest.main()
