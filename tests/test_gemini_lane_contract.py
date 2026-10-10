from datetime import datetime, timedelta, timezone
import types
import unittest
from unittest.mock import patch

import run260_gemini_model_routing as run260


class GeminiLaneContractTests(unittest.TestCase):
    def _row(self, model, outcome, *, minutes_ago=0, error_type=""):
        return {
            "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(),
            "model": model,
            "kind": "screening_batch" if "lite" in model else "deep_dive",
            "outcome": outcome,
            "error_type": error_type,
        }

    def _fake_pipeline(self, history=None):
        calls = []
        module = None

        def original(*args, **kwargs):
            calls.append((args, kwargs))
            pool = list(args[4] if len(args) >= 5 else kwargs.get("pool") or [])
            if not pool:
                raise NoAvailableModelError("no model")
            return "response", pool[0]

        class NoAvailableModelError(Exception):
            pass

        def original_screening(prompt, config=None, kind="screening", reserve=0, request_context=""):
            return module._call_model_pool(
                prompt, config, kind, reserve, module.SCREENING_MODEL_POOL,
                deep_dive=False, request_context=request_context,
            )

        def original_deep_dive(prompt, config=None, kind="deep_dive", request_context="", request_origin="new"):
            return module._call_model_pool(
                prompt, config, kind, 0, module.DEEP_DIVE_MODEL_POOL,
                deep_dive=True, request_context=request_context, request_origin=request_origin,
            )

        module = types.SimpleNamespace(
            _call_model_pool=original,
            _call_screening_pool=original_screening,
            _call_deep_dive_pool=original_deep_dive,
            SCREENING_MODEL_POOL=[
                "gemini-3.1-flash-lite",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
            ],
            SCREENING_MODEL_CANDIDATES=[
                "gemini-3.1-flash-lite",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
            ],
            DEEP_DIVE_MODEL_POOL=["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash"],
            DEEP_DIVE_MODEL_CANDIDATES=[],
            MODEL_DAILY_BUDGETS={},
            PERSISTENT_GEMINI_COUNTER=types.SimpleNamespace(model_budgets={}),
            PROVIDER_HEALTH_HISTORY_OVERRIDE=list(history or []),
            SESSION_UNAVAILABLE_MODELS=set(),
            SESSION_EXHAUSTED_MODELS=set(),
            NoAvailableModelError=NoAvailableModelError,
        )
        return module, calls

    def test_screening_lane_is_canonical_lite_only(self):
        module, _ = self._fake_pipeline()
        run260.install(module)
        self.assertEqual(
            module.SCREENING_MODEL_POOL,
            ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"],
        )
        self.assertTrue(all(model.endswith("-flash-lite") for model in module.SCREENING_MODEL_POOL))

    def test_lite_health_can_reorder_only_inside_screening_lane(self):
        history = [
            self._row("gemini-3.5-flash-lite", "error", error_type="ServiceUnavailable"),
            self._row("gemini-3.5-flash-lite", "error", error_type="ReadTimeout"),
            self._row("gemini-3.1-flash-lite", "success"),
            self._row("gemini-3.1-flash-lite", "success"),
            self._row("gemini-3.8-flash", "success"),
        ]
        module, calls = self._fake_pipeline(history)
        run260.install(module)
        module._call_screening_pool("prompt", None, "screening_batch")
        routed = list(calls[-1][0][4])
        self.assertEqual(routed[0], "gemini-3.1-flash-lite")
        self.assertEqual(set(routed), {"gemini-3.5-flash-lite", "gemini-3.1-flash-lite"})
        self.assertNotIn("gemini-3.8-flash", routed)

    def test_health_backstop_is_scoped_to_requested_lane(self):
        history = [
            self._row("gemini-3.5-flash-lite", "error", minutes_ago=30, error_type="ServiceUnavailable"),
            self._row("gemini-3.1-flash-lite", "success", minutes_ago=1800),
            self._row("gemini-3.1-flash-lite", "success", minutes_ago=1860),
            self._row("gemini-3.6-flash", "success", minutes_ago=5),
            self._row("gemini-3.5-flash", "success", minutes_ago=6),
            self._row("gemini-3.7-flash", "success", minutes_ago=7),
            self._row("gemini-3.8-flash", "success", minutes_ago=8),
        ]
        with patch.dict(run260.os.environ, {"GEMINI_PROVIDER_HEALTH_RECENT_ATTEMPTS": "4"}, clear=False):
            stats = run260._model_health_stats(run260.DEFAULT_SCREENING_POOL, history)
        self.assertEqual(stats["gemini-3.1-flash-lite"]["attempts"], 2)
        self.assertEqual(stats["gemini-3.5-flash-lite"]["attempts"], 1)

    def test_live_screening_health_routing_survives_later_provider_wrapper_replacement(self):
        history = [
            self._row("gemini-3.5-flash-lite", "error", error_type="ServiceUnavailable"),
            self._row("gemini-3.1-flash-lite", "success"),
            self._row("gemini-3.1-flash-lite", "success"),
        ]
        module, _ = self._fake_pipeline(history)
        run260.install(module)
        live_calls = []

        def later_provider_pool(*args, **kwargs):
            live_calls.append((args, kwargs))
            return "live", args[4][0]

        module._call_model_pool = later_provider_pool
        result = module._call_screening_pool("prompt", None, "global_calibration")
        self.assertEqual(result, ("live", "gemini-3.1-flash-lite"))
        self.assertEqual(live_calls[0][0][4][0], "gemini-3.1-flash-lite")
        self.assertTrue(all("lite" in model for model in live_calls[0][0][4]))

    def test_article_lane_never_contains_lite_models(self):
        self.assertTrue(run260.ARTICLE_MODELS)
        self.assertTrue(all("lite" not in model for model in run260.ARTICLE_MODELS))
        ranked = run260._health_ranked_pool(
            ["gemini-3.5-flash-lite", *run260.DEFAULT_DEEP_DIVE_POOL],
            [self._row("gemini-3.5-flash-lite", "success")],
        )
        self.assertNotIn("gemini-3.5-flash-lite", ranked)
        self.assertTrue(all("lite" not in model for model in ranked))


if __name__ == "__main__":
    unittest.main()
