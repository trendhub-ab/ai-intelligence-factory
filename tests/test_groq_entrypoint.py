import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import production_pipeline


class EntrypointTests(unittest.TestCase):
    def test_saved_prompt_lane_does_not_import_gemini_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            fixture.write_text(json.dumps({"stage": "calibration", "prompt": "offline example", "max_output_tokens": 100}))
            env = {"AIIF_ONE_SHOT_MODE": "groq_saved_prompt_validation", "AIIF_GROQ_FIXTURE": str(fixture)}
            with patch.dict(os.environ, env, clear=True), patch.dict(sys.modules, {"pipeline": None}):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    production_pipeline.main()
            self.assertEqual(json.loads(output.getvalue())["provider_calls"], 0)
