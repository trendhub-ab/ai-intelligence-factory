import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import run260_gemini_model_routing as run260


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
        audit = types.SimpleNamespace(records=[])

        class NoAvailableModelError(Exception):
            pass

        def original(*args, **kwargs):
            calls.append((args, kwargs))
            if not args[4]:
                raise NoAvailableModelError("no available model")
            return "response", args[4][0]

        def generate(model_name, prompt, config=None, request_kind="other", reserve=0,
                     request_context="", count_as_deep_dive=False, request_origin="new"):
            audit.records.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": model_name,
                "kind": request_kind,
                "outcome": "success",
                "error_type": "",
            })
            return "provider-response"

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
            _generate_via_chat=generate,
            GEMINI_USAGE_AUDIT=audit,
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

    def test_lite_provider_outcome_is_persisted_even_below_pool_wrappers(self):
        module, _ = self._fake_pipeline()
        run260.install(module)
        with patch.object(run260, "_persist_provider_health_history") as persist:
            result = module._generate_via_chat(
                "gemini-3.1-flash-lite",
                "prompt",
                request_kind="screening_batch",
            )
        self.assertEqual(result, "provider-response")
        self.assertEqual(module._provider_health_history[-1]["model"], "gemini-3.1-flash-lite")
        self.assertEqual(module._provider_health_history[-1]["outcome"], "success")
        persist.assert_called_once_with(module)

    def test_article_lane_still_rejects_lite_models(self):
        ranked = run260._health_ranked_pool(
            ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash"],
            [],
        )
        self.assertEqual(ranked, ["gemini-3.6-flash"])


if __name__ == "__main__":
    unittest.main()
