import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

import run260_gemini_model_routing as run260


ROOT = Path(__file__).resolve().parents[1]


class GeminiLaneIsolationTests(unittest.TestCase):
    def _row(self, model, outcome, error_type=""):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "kind": "screening_batch",
            "outcome": outcome,
            "error_type": error_type,
        }

    def _fake_pipeline(self, history=None):
        calls = []

        class NoAvailableModelError(Exception):
            pass

        def original(*args, **kwargs):
            calls.append((args, kwargs))
            if not args[4]:
                raise NoAvailableModelError("no available model")
            return "response", args[4][0]

        module = None

        def original_deep_dive(prompt, config=None, kind="deep_dive", request_context="", request_origin="new"):
            return module._call_model_pool(
                prompt,
                config,
                kind,
                0,
                module.DEEP_DIVE_MODEL_POOL,
                deep_dive=True,
                request_context=request_context,
                request_origin=request_origin,
            )

        persistent = types.SimpleNamespace(model_budgets={
            "gemini-3.5-flash-lite": 450,
            "gemini-3.1-flash-lite": 450,
        })
        module = types.SimpleNamespace(
            _call_model_pool=original,
            _call_deep_dive_pool=original_deep_dive,
            SCREENING_MODEL_POOL=[
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-3.6-flash",
            ],
            SCREENING_MODEL_CANDIDATES=[
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-3.6-flash",
            ],
            DEEP_DIVE_MODEL_POOL=["gemini-3.6-flash", "gemini-3.8-flash"],
            DEEP_DIVE_MODEL_CANDIDATES=["gemini-3.6-flash", "gemini-3.8-flash"],
            MODEL_DAILY_BUDGETS={
                "gemini-3.5-flash-lite": 450,
                "gemini-3.1-flash-lite": 450,
                "gemini-3.6-flash": 18,
                "gemini-3.7-flash": 18,
                "gemini-3.8-flash": 18,
                "gemini-3.5-flash": 18,
            },
            PERSISTENT_GEMINI_COUNTER=persistent,
            PROVIDER_HEALTH_HISTORY_OVERRIDE=list(history or []),
            SESSION_UNAVAILABLE_MODELS=set(),
            SESSION_EXHAUSTED_MODELS=set(),
            NoAvailableModelError=NoAvailableModelError,
        )
        return module, calls

    def test_daily_workflow_screening_pool_is_lite_only(self):
        text = (ROOT / ".github" / "workflows" / "daily-one-shot.yml").read_text(encoding="utf-8")
        self.assertIn(
            'GEMINI_SCREENING_MODEL_CANDIDATES: "gemini-3.5-flash-lite,gemini-3.1-flash-lite"',
            text,
        )

    def test_pipeline_default_screening_pool_contains_both_lite_models_only(self):
        text = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn(
            '"gemini-3.5-flash-lite,gemini-3.1-flash-lite"',
            text,
        )

    def test_screening_health_routing_reorders_only_within_lite_lane(self):
        history = [
            self._row("gemini-3.5-flash-lite", "error", "ServiceUnavailable"),
            self._row("gemini-3.5-flash-lite", "error", "ReadTimeout"),
            self._row("gemini-3.1-flash-lite", "success"),
            self._row("gemini-3.1-flash-lite", "success"),
            self._row("gemini-3.6-flash", "success"),
        ]
        ranked = run260._health_ranked_screening_pool(
            [
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-3.6-flash",
            ],
            history,
        )
        self.assertEqual(ranked, ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"])

    def test_install_strips_flash_from_screening_and_applies_lite_health_order(self):
        history = [
            self._row("gemini-3.5-flash-lite", "error", "ServiceUnavailable"),
            self._row("gemini-3.1-flash-lite", "success"),
            self._row("gemini-3.1-flash-lite", "success"),
        ]
        module, _ = self._fake_pipeline(history)
        run260.install(module)
        self.assertEqual(
            module.SCREENING_MODEL_POOL,
            ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"],
        )
        self.assertTrue(all("flash-lite" in model for model in module.SCREENING_MODEL_POOL))

    def test_screening_batch_and_global_calibration_never_cross_into_flash_lane(self):
        history = [
            self._row("gemini-3.5-flash-lite", "error", "ServiceUnavailable"),
            self._row("gemini-3.1-flash-lite", "success"),
        ]
        module, calls = self._fake_pipeline(history)
        run260.install(module)

        module._call_model_pool(
            "screen",
            None,
            "screening_batch",
            0,
            ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash"],
            deep_dive=False,
        )
        module._call_model_pool(
            "calibrate",
            None,
            "global_calibration",
            0,
            ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"],
            deep_dive=False,
        )

        self.assertEqual(len(calls), 2)
        for args, _kwargs in calls:
            self.assertEqual(args[4], ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"])
            self.assertTrue(all("flash-lite" in model for model in args[4]))

    def test_article_lane_still_rejects_lite_models(self):
        ranked = run260._health_ranked_pool(
            ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash"],
            [],
        )
        self.assertEqual(ranked, ["gemini-3.6-flash"])


if __name__ == "__main__":
    unittest.main()
