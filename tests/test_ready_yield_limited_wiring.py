"""Provider-free integration checks for the bounded experiment entrypoint."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments import ready_yield_fixed_evidence as experiment


class LimitedWiringTests(unittest.TestCase):
    def test_isolated_probe_restores_partitioned_budget_without_exceeding_original(self):
        budget = SimpleNamespace(budget=0, used=0)
        budget.can_request = lambda: budget.used + 1 <= budget.budget
        pipeline = SimpleNamespace(_run346_original_deep_dive_budget=4,
                                   DEEP_DIVE_MODEL_BUDGET=budget)
        experiment.prepare_isolated_probe_budget(pipeline)
        self.assertEqual(pipeline.DEEP_DIVE_MODEL_BUDGET.budget, 3)

    @staticmethod
    def _shared(reservations):
        return SimpleNamespace(reserve=lambda model, now: reservations.append(model) or 0)

    def test_two_503s_stop_without_fallback_or_hidden_retry(self):
        calls = []
        reservations = []
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
            rows = experiment.execute_limited(pipeline, {}, Path(out), self._shared(reservations),
                clock=self._clock(), sleep=lambda seconds: None)
            self.assertEqual(calls, ["gemini-3.6-flash", "gemini-3.5-flash"])
            self.assertEqual(reservations, calls)
            self.assertEqual([r["outcome"] for r in rows], ["503", "503"])
            self.assertEqual(json.loads((Path(out) / "summary.json").read_text())["provider_attempts"], 2)

    def test_saves_raw_before_gate_evaluation(self):
        with TemporaryDirectory() as out:
            reservations = []
            def evaluate(p, raw, info):
                self.assertTrue(list(Path(out).glob("*.raw.txt")))
                return {"gate": {"ready_eligible_before_persistence": True}}
            pipeline = SimpleNamespace(
                _generate_via_chat=lambda *a, **kw: SimpleNamespace(text="RAW ARTICLE"),
                GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS=4096,
            )
            with patch.object(experiment, "prompt_for", return_value="prompt"), \
                 patch.object(experiment, "evaluate", side_effect=evaluate):
                rows = experiment.execute_limited(pipeline, {}, Path(out), self._shared(reservations),
                    clock=self._clock(), sleep=lambda seconds: None)
            self.assertEqual(len(rows), 4)
            self.assertEqual(len(reservations), 4)
            self.assertEqual(len(list(Path(out).glob("*.raw.txt"))), 4)

    def test_unavailable_shared_ledger_prevents_provider_send(self):
        calls = []
        pipeline = SimpleNamespace(
            _generate_via_chat=lambda *a, **kw: calls.append(1),
            GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS=4096,
        )
        def blocked(model, now):
            raise RuntimeError("ledger unavailable")
        with TemporaryDirectory() as out:
            with patch.object(experiment, "prompt_for", return_value="prompt"):
                rows = experiment.execute_limited(pipeline, {}, Path(out),
                    SimpleNamespace(reserve=blocked), clock=self._clock(), sleep=lambda seconds: None)
            self.assertEqual(calls, [])
            self.assertEqual(rows[0]["provider_attempted"], False)
            self.assertEqual(json.loads((Path(out) / "summary.json").read_text())["provider_attempts"], 0)

    def test_recovery_tries_each_model_once_without_feedback(self):
        calls = []
        pipeline = SimpleNamespace(
            _generate_via_chat=lambda model, *a, **kw: (calls.append(model) or SimpleNamespace(text="ARTICLE")),
            GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS=4096,
        )
        with TemporaryDirectory() as out, \
             patch.object(experiment, "prompt_for", return_value="prompt"), \
             patch.object(experiment, "evaluate", return_value={
                 "gate": {"ready_eligible_before_persistence": False}, "body_after_polish": "ARTICLE"}):
            rows = experiment.execute_limited(pipeline, {}, Path(out), self._shared([]),
                max_attempts=2, initial_only=True, clock=self._clock(), sleep=lambda seconds: None)
        self.assertEqual(calls, ["gemini-3.6-flash", "gemini-3.5-flash"])
        self.assertEqual(len(rows), 2)

    @staticmethod
    def _clock():
        # 25 seconds apart, avoiding real waits in a zero-provider test.
        time = iter((0, 0, 25, 25, 50, 50, 75, 75))
        return lambda: next(time)
