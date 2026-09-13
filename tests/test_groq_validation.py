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
from groq_validation import reserve_attempt, run_saved_prompt_validation


class ValidationTests(unittest.TestCase):
    def test_persistent_caps_and_rolling_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = str(Path(directory) / "usage.sqlite")
            reserve_attempt(ledger, 4000, 100000)
            with self.assertRaisesRegex(ProviderError, "minute_budget"):
                reserve_attempt(ledger, SAFE_TPM - 3999, 100010)
            reserve_attempt(ledger, 3000, 100010)

            # Build daily usage while keeping each request in a separate minute.
            stamp = 100100
            used = 7000
            index = 0
            while used + 6000 <= SAFE_TPD:
                reserve_attempt(ledger, 6000, stamp)
                used += 6000
                stamp += 61
                index += 1
            with self.assertRaisesRegex(ProviderError, "daily_budget"):
                reserve_attempt(ledger, SAFE_TPD - used + 1, stamp)

            # Once the rolling 24h window has moved past all previous reservations,
            # capacity becomes available again.
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
