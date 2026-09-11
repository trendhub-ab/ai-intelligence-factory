import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ai_provider import ProviderError
from groq_validation import reserve_attempt, run_saved_prompt_validation


class ValidationTests(unittest.TestCase):
    def test_persistent_cap_and_rolling_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = str(Path(directory) / "usage.sqlite")
            reserve_attempt(ledger, 8000, 100000)
            with self.assertRaisesRegex(ProviderError, "pacing"):
                reserve_attempt(ledger, 8000, 100010)
            reserve_attempt(ledger, 8000, 100100)
            reserve_attempt(ledger, 8000, 100200)
            with self.assertRaisesRegex(ProviderError, "persistent_validation_budget"):
                reserve_attempt(ledger, 1, 100300)
            reserve_attempt(ledger, 8000, 200000)

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

    def test_live_without_key_fails_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            fixture.write_text(json.dumps({"stage": "article", "prompt": "test", "max_output_tokens": 100}))
            with patch.dict(os.environ, {"AIIF_GROQ_FIXTURE": str(fixture), "AIIF_GROQ_LIVE": "true"}, clear=True):
                with self.assertRaisesRegex(ProviderError, "groq_key_and_persistent_ledger"):
                    run_saved_prompt_validation()
