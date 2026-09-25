"""Provider-free integration checks for the bounded experiment entrypoint."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments import ready_yield_fixed_evidence as experiment


class LimitedWiringTests(unittest.TestCase):
    def test_two_503s_stop_without_fallback_or_hidden_retry(self):
        calls = []
        def generate(model, prompt, **kwargs):
            calls.append(model)
            error = RuntimeError("503 UNAVAILABLE")
            error.code = 503
            raise error
        pipeline = SimpleNamespace(
            _generate_via_chat=generate,
            GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS=4096,
            GATE_SEVERITY_HARD="HARD", GATE_SEVERITY_REVIEW="REVIEW",
        )
        with TemporaryDirectory() as out, \
             patch.object(experiment, "prompt_for", return_value="prompt"):
            rows = experiment.execute_limited(pipeline, {}, Path(out),
                clock=self._clock(), sleep=lambda seconds: None)
            self.assertEqual(calls, ["gemini-3.6-flash", "gemini-3.5-flash"])
            self.assertEqual([r["outcome"] for r in rows], ["503", "503"])
            self.assertEqual(json.loads((Path(out) / "summary.json").read_text())["provider_attempts"], 2)

    def test_saves_raw_before_gate_evaluation(self):
        with TemporaryDirectory() as out:
            def evaluate(p, raw, info):
                self.assertTrue(list(Path(out).glob("*.raw.txt")))
                return {"gate": {"ready_eligible_before_persistence": True}}
            pipeline = SimpleNamespace(
                _generate_via_chat=lambda *a, **kw: SimpleNamespace(text="RAW ARTICLE"),
                GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS=4096,
            )
            with patch.object(experiment, "prompt_for", return_value="prompt"), \
                 patch.object(experiment, "evaluate", side_effect=evaluate):
                rows = experiment.execute_limited(pipeline, {}, Path(out),
                    clock=self._clock(), sleep=lambda seconds: None)
            self.assertEqual(len(rows), 4)
            self.assertEqual(len(list(Path(out).glob("*.raw.txt"))), 4)

    @staticmethod
    def _clock():
        # 25 seconds apart, avoiding real waits in a zero-provider test.
        time = iter((0, 0, 25, 25, 50, 50, 75, 75))
        return lambda: next(time)
