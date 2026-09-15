import os
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import run260_gemini_model_routing as run260


class Run260GeminiModelRoutingTests(unittest.TestCase):
    def _fake_pipeline(self, pool=None, history=None):
        calls = []
        deep_dive_calls = []

        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return "response", "model"

        module = None

        def original_deep_dive(prompt, config=None, kind="deep_dive", request_context="", request_origin="new"):
            deep_dive_calls.append((prompt, config, kind, request_context, request_origin))
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

        persistent = types.SimpleNamespace(model_budgets={})
        module = types.SimpleNamespace(
            _call_model_pool=original,
            _call_deep_dive_pool=original_deep_dive,
            DEEP_DIVE_MODEL_POOL=list(pool or ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash"]),
            DEEP_DIVE_MODEL_CANDIDATES=list(pool or []),
            MODEL_DAILY_BUDGETS={
                "gemini-3.6-flash": 18,
                "gemini-3.7-flash": 18,
                "gemini-3.8-flash": 18,
                "gemini-3.5-flash": 18,
            },
            PERSISTENT_GEMINI_COUNTER=persistent,
            PROVIDER_HEALTH_HISTORY_OVERRIDE=list(history or []),
        )
        return module, calls, deep_dive_calls

    def _row(self, model, outcome, *, hours_ago=0, kind="deep_dive", error_type=""):
        ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {
            "timestamp": ts.isoformat(),
            "model": model,
            "kind": kind,
            "outcome": outcome,
            "error_type": error_type,
        }

    def test_cold_start_is_36_then_35_then_37_then_38(self):
        module, _, _ = self._fake_pipeline()
        run260.install(module)
        self.assertEqual(
            module.DEEP_DIVE_MODEL_POOL[:4],
            [
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
            ],
        )

    def test_quality_retry_cold_start_prefers_36_then_35_and_stays_bounded(self):
        module, calls, _ = self._fake_pipeline()
        run260.install(module)
        result = module._call_model_pool(
            "prompt", None, "quality_retry", 0, module.DEEP_DIVE_MODEL_POOL,
            deep_dive=True, request_context="unit",
        )
        self.assertEqual(result, ("response", "model"))
        self.assertEqual(len(calls), 1)
        routed_pool = calls[0][0][4]
        self.assertEqual(routed_pool, ["gemini-3.6-flash", "gemini-3.5-flash"])
        self.assertEqual(len(routed_pool), run260.QUALITY_RETRY_MAX_DISTINCT_MODELS)

    def test_health_history_reorders_by_smoothed_success_rate(self):
        history = [
            self._row("gemini-3.6-flash", "error", error_type="ServiceUnavailable"),
            self._row("gemini-3.6-flash", "error", error_type="ReadTimeout"),
            self._row("gemini-3.5-flash", "success"),
            self._row("gemini-3.5-flash", "success"),
            self._row("gemini-3.7-flash", "success"),
            self._row("gemini-3.8-flash", "error", error_type="ServiceUnavailable"),
        ]
        ranked = run260._health_ranked_pool(list(run260.DEFAULT_DEEP_DIVE_POOL), history)
        self.assertEqual(ranked[0], "gemini-3.5-flash")
        self.assertEqual(ranked[1], "gemini-3.7-flash")
        self.assertLess(ranked.index("gemini-3.8-flash"), ranked.index("gemini-3.6-flash"))

    def test_health_routing_is_applied_on_live_fresh_deep_dive_path(self):
        history = [
            self._row("gemini-3.6-flash", "error"),
            self._row("gemini-3.5-flash", "success"),
            self._row("gemini-3.5-flash", "success"),
        ]
        module, calls, deep_dive_calls = self._fake_pipeline(history=history)
        run260.install(module)
        module._call_deep_dive_pool("prompt", None, "deep_dive", request_context="fresh")
        self.assertEqual(len(deep_dive_calls), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][4][0], "gemini-3.5-flash")
        self.assertEqual(len(calls[0][0][4]), 4)

    def test_live_deep_dive_quality_retry_path_uses_healthiest_two_models(self):
        history = [
            self._row("gemini-3.6-flash", "error"),
            self._row("gemini-3.5-flash", "success"),
            self._row("gemini-3.7-flash", "success"),
            self._row("gemini-3.8-flash", "error"),
        ]
        module, calls, deep_dive_calls = self._fake_pipeline(history=history)
        run260.install(module)
        result = module._call_deep_dive_pool(
            "prompt",
            {"max_output_tokens": 9000},
            "quality_retry",
            request_context="live-path",
            request_origin="new",
        )
        self.assertEqual(result, ("response", "model"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(deep_dive_calls), 0, "quality retry must use Run261 live-path guard")
        self.assertEqual(calls[0][0][4], ["gemini-3.5-flash", "gemini-3.7-flash"])
        self.assertTrue(calls[0][1]["deep_dive"])
        self.assertEqual(calls[0][1]["request_context"], "live-path")
        self.assertEqual(calls[0][1]["request_origin"], "new")

    def test_quality_retry_preserves_a_second_distinct_model_for_rescue(self):
        module, calls, _ = self._fake_pipeline()
        run260.install(module)
        module._call_deep_dive_pool("prompt", None, "quality_retry")
        self.assertEqual(len(calls[0][0][4]), 2)
        self.assertNotEqual(calls[0][0][4][0], calls[0][0][4][1])

    def test_recent_n_backstop_uses_older_attempts_when_24h_window_is_sparse(self):
        history = [
            self._row("gemini-3.6-flash", "error", hours_ago=1),
            self._row("gemini-3.5-flash", "success", hours_ago=30),
            self._row("gemini-3.5-flash", "success", hours_ago=31),
            self._row("gemini-3.7-flash", "error", hours_ago=32),
            self._row("gemini-3.8-flash", "error", hours_ago=33),
        ]
        with patch.dict(os.environ, {"GEMINI_PROVIDER_HEALTH_RECENT_ATTEMPTS": "4"}, clear=False):
            ranked = run260._health_ranked_pool(list(run260.DEFAULT_DEEP_DIVE_POOL), history)
        self.assertEqual(ranked[0], "gemini-3.5-flash")

    def test_normal_non_deep_dive_pool_is_not_reordered(self):
        module, calls, _ = self._fake_pipeline()
        run260.install(module)
        module._call_model_pool(
            "prompt", None, "other", 0,
            ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"],
            deep_dive=False,
        )
        self.assertEqual(calls[0][0][4][0], "gemini-3.8-flash")

    def test_quality_repair_aliases_get_same_two_model_bound(self):
        for kind in ("quality_repair", "quality_rescue", "recompose", "reader_repair"):
            with self.subTest(kind=kind):
                module, calls, _ = self._fake_pipeline()
                run260.install(module)
                module._call_model_pool("prompt", None, kind, 0, module.DEEP_DIVE_MODEL_POOL, deep_dive=True)
                self.assertEqual(len(calls[0][0][4]), 2)

    def test_38_budget_is_explicit_and_cannot_exceed_18(self):
        module, _, _ = self._fake_pipeline()
        with patch.dict(os.environ, {"GEMINI_38_FLASH_DAILY_BUDGET": "999"}, clear=False):
            run260.install(module)
        self.assertEqual(module.MODEL_DAILY_BUDGETS["gemini-3.8-flash"], 18)
        self.assertEqual(module.PERSISTENT_GEMINI_COUNTER.model_budgets["gemini-3.8-flash"], 18)

    def test_operator_can_lower_38_budget(self):
        module, _, _ = self._fake_pipeline()
        with patch.dict(os.environ, {"GEMINI_38_FLASH_DAILY_BUDGET": "7"}, clear=False):
            run260.install(module)
        self.assertEqual(module.MODEL_DAILY_BUDGETS["gemini-3.8-flash"], 7)

    def test_screening_pool_and_gate_surfaces_are_not_touched(self):
        module, _, _ = self._fake_pipeline()
        module.SCREENING_MODEL_POOL = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
        module.MIN_PAID_AREA_LENGTH = 1200
        module.MAX_QUALITY_RETRIES = 1
        before_screening = list(module.SCREENING_MODEL_POOL)
        before_gate = (module.MIN_PAID_AREA_LENGTH, module.MAX_QUALITY_RETRIES)
        run260.install(module)
        self.assertEqual(module.SCREENING_MODEL_POOL, before_screening)
        self.assertEqual((module.MIN_PAID_AREA_LENGTH, module.MAX_QUALITY_RETRIES), before_gate)

    def test_health_state_contains_no_prompt_or_article_content(self):
        row = run260._normalize_health_record({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "gemini-3.6-flash",
            "kind": "deep_dive",
            "outcome": "error",
            "error_type": "ReadTimeout",
            "context": "SECRET ARTICLE TITLE",
            "prompt": "SECRET PROMPT",
        })
        self.assertIsNotNone(row)
        self.assertNotIn("context", row)
        self.assertNotIn("prompt", row)

    def test_install_is_idempotent_for_both_live_entrypoints(self):
        module, _, _ = self._fake_pipeline()
        run260.install(module)
        wrapped_pool = module._call_model_pool
        wrapped_deep_dive = module._call_deep_dive_pool
        run260.install(module)
        self.assertIs(module._call_model_pool, wrapped_pool)
        self.assertIs(module._call_deep_dive_pool, wrapped_deep_dive)


if __name__ == "__main__":
    unittest.main()
