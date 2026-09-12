import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ai_provider import ProviderError
from groq_rate_policy import SAFE_TPD, SAFE_TPM
from groq_validation import (
    _safe_http_error_diagnostic,
    _sanitize_provider_error_message,
    reserve_attempt,
    run_saved_prompt_validation,
)


class ValidationTests(unittest.TestCase):
    def test_persistent_caps_and_rolling_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = str(Path(directory) / "usage.sqlite")
            reserve_attempt(ledger, 4000, 100000)
            with self.assertRaisesRegex(ProviderError, "minute_budget"):
                reserve_attempt(ledger, SAFE_TPM - 3999, 100010)
            reserve_attempt(ledger, 3000, 100010)

            stamp = 100100
            used = 7000
            while used + 6000 <= SAFE_TPD:
                reserve_attempt(ledger, 6000, stamp)
                used += 6000
                stamp += 61
            with self.assertRaisesRegex(ProviderError, "daily_budget"):
                reserve_attempt(ledger, SAFE_TPD - used + 1, stamp)
            reserve_attempt(ledger, 1000, stamp + 86401)

    def test_offline_never_opens_network(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            fixture.write_text(json.dumps({"stage": "calibration", "prompt": "test", "max_output_tokens": 100}))
            with patch.dict(os.environ, {"AIIF_GROQ_FIXTURE": str(fixture), "AIIF_GROQ_LIVE": "false"}, clear=True):
                with patch("urllib.request.build_opener", side_effect=AssertionError("network")):
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = run_saved_prompt_validation()
            self.assertEqual(result["provider_calls"], 0)
            self.assertFalse(result["quality_validated"])
            self.assertEqual(result["safety_budget"]["tpm"], SAFE_TPM)

    def test_live_without_key_fails_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            fixture.write_text(json.dumps({"stage": "article", "prompt": "test", "max_output_tokens": 100}))
            with patch.dict(os.environ, {"AIIF_GROQ_FIXTURE": str(fixture), "AIIF_GROQ_LIVE": "true"}, clear=True):
                with self.assertRaisesRegex(ProviderError, "groq_key_and_persistent_ledger"):
                    run_saved_prompt_validation()

    def test_error_message_sanitizer_redacts_sensitive_surfaces(self):
        raw=("Bad schema at https://example.com/schema Authorization: Bearer SECRET123 "
             "api_key=gsk_supersecret token=abc123\n" + "x"*500)
        clean=_sanitize_provider_error_message(raw)
        self.assertLessEqual(len(clean),300)
        for secret in ("SECRET123","gsk_supersecret","abc123","https://example.com/schema"):
            self.assertNotIn(secret,clean)
        self.assertIn("[URL]",clean)
        self.assertIn("[REDACTED]",clean)

    def test_safe_diagnostic_whitelists_only_error_metadata(self):
        payload={
            "error":{
                "type":"invalid_request_error",
                "code":"json_validate_failed",
                "param":"response_format",
                "message":"Schema error at https://example.com/schema",
                "failed_generation":"TOP SECRET MODEL OUTPUT",
                "request":"PROMPT SECRET",
            },
            "other":"secret",
        }
        diagnostic=_safe_http_error_diagnostic(payload)
        self.assertEqual(diagnostic["type"],"invalid_request_error")
        self.assertEqual(diagnostic["code"],"json_validate_failed")
        self.assertEqual(diagnostic["param"],"response_format")
        self.assertIn("[URL]",diagnostic["message"])
        serialized=json.dumps(diagnostic)
        self.assertNotIn("TOP SECRET",serialized)
        self.assertNotIn("PROMPT SECRET",serialized)
        self.assertNotIn("failed_generation",serialized)

    def test_safe_diagnostic_rejects_nonstandard_shapes(self):
        self.assertEqual(_safe_http_error_diagnostic(None),{})
        self.assertEqual(_safe_http_error_diagnostic({"error":"bad"}),{})
        self.assertEqual(_safe_http_error_diagnostic({"message":"outside error"}),{})
