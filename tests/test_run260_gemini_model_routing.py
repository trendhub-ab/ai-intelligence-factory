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
            SESSION_UNAVAILABLE_MODELS=set(),
            SESSION_EXHAUSTED_MODELS=set(),
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

    def test_cold_start_contains_all_six_health_routed_article_models(self):
        module, _, _ = self._fake_pipeline()
        run260.install(module)
        self.assertEqual(
            module.DEEP_DIVE_MODEL_POOL[:6],
            [
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "gemini-3-flash-preview",
                "gemini-2.5-flash",
            ],
        )
        self.assertEqual(set(module.DEEP_DIVE_MODEL_POOL[:6]), set(run260.ARTICLE_MODELS))

    def test_new_models_participate_in_health_ranking(self):
        history = [
            self._row("gemini-3.6-flash", "error", error_type="ServiceUnavailable"),
            self._row("gemini-3.5-flash", "error", error_type="ReadTimeout"),
            self._row("gemini-3.7-flash", "error", error_type="ServiceUnavailable"),
            self._row("gemini-3.8-flash", "error", error_type="ServiceUnavailable"),
            self._row("gemini-3-flash-preview", "success"),
            self._row("gemini-3-flash-preview", "success"),
            self._row("gemini-2.5-flash", "success"),
        ]
        ranked = run260._health_ranked_pool(list(run260.DEFAULT_DEEP_DIVE_POOL), history)
        self.assertEqual(ranked[0], "gemini-3-flash-preview")
        self.assertEqual(ranked[1], "gemini-2.5-flash")

    def test_new_model_budgets_are_explicit_and_capped_at_18(self):
        module, _, _ = self._fake_pipeline()
        with patch.dict(
            os.environ,
            {
                "GEMINI_3_FLASH_DAILY_BUDGET": "999",
                "GEMINI_25_FLASH_DAILY_BUDGET": "999",
            },
            clear=False,
        ):
            run260.install(module)
        self.assertEqual(module.MODEL_DAILY_BUDGETS["gemini-3-flash-preview"], 18)
        self.assertEqual(module.MODEL_DAILY_BUDGETS["gemini-2.5-flash"], 18)
        self.assertEqual(module.PERSISTENT_GEMINI_COUNTER.model_budgets["gemini-3-flash-preview"], 18)
        self.assertEqual(module.PERSISTENT_GEMINI_COUNTER.model_budgets["gemini-2.5-flash"], 18)

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

    def test_health_routing_survives_later_provider_pool_replacement_on_fresh_deep_dive(self):
        history = [
            self._row("gemini-3.6-flash", "error"),
            self._row("gemini-3.5-flash", "success"),
            self._row("gemini-3.5-flash", "success"),
        ]
        module, calls, deep_dive_calls = self._fake_pipeline(history=history)
        run260.install(module)

        # Mirrors canonical Production order: Run172/303 replace _call_model_pool after
        # Run260, while Run260's Deep Dive entrypoint remains in the wrapper chain.
        live_calls = []

        def later_provider_pool(*args, **kwargs):
            live_calls.append((args, kwargs))
            return "live-response", "gemini-3.5-flash"

        module._call_model_pool = later_provider_pool
        result = module._call_deep_dive_pool("prompt", None, "deep_dive", request_context="fresh")
        self.assertEqual(result, ("live-response", "gemini-3.5-flash"))
        self.assertEqual(len(deep_dive_calls), 0)
        self.assertEqual(len(calls), 0)
        self.assertEqual(len(live_calls), 1)
        self.assertEqual(live_calls[0][0][4][0], "gemini-3.5-flash")
        self.assertEqual(len(live_calls[0][0][4]), 4)

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
        routed = calls[0][0][4]
        self.assertEqual(len(routed), 2)
        self.assertEqual(set(routed), {"gemini-3.5-flash", "gemini-3.7-flash"})
        self.assertTrue(calls[0][1]["deep_dive"])
        self.assertEqual(calls[0][1]["request_context"], "live-path")
        self.assertEqual(calls[0][1]["request_origin"], "new")

    def test_run57_unavailable_top_models_do_not_strand_healthy_quality_fallback(self):
        history = [
            self._row("gemini-3.6-flash", "success"),
            self._row("gemini-3.6-flash", "success"),
            self._row("gemini-3.6-flash", "success"),
            self._row("gemini-3.6-flash", "error", error_type="ServiceUnavailable"),
            self._row("gemini-3.5-flash", "error", error_type="ServiceUnavailable"),
            self._row("gemini-3.7-flash", "success"),
            self._row("gemini-3.8-flash", "error", error_type="ServiceUnavailable"),
        ]
        module, calls, _ = self._fake_pipeline(history=history)
        run260.install(module)
        module.SESSION_UNAVAILABLE_MODELS.update({"gemini-3.6-flash", "gemini-3.5-flash"})

        result = module._call_deep_dive_pool("repair", None, "quality_retry", request_context="run57")
        self.assertEqual(result, ("response", "model"))
        self.assertEqual(calls[0][0][4], ["gemini-3.7-flash", "gemini-3.8-flash"])
        self.assertEqual(len(calls[0][0][4]), 2)

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

    def test_live_deep_dive_captures_real_usage_audit_after_later_pool_replacement(self):
        module, _, _ = self._fake_pipeline()
        module.GEMINI_USAGE_AUDIT = types.SimpleNamespace(records=[])
        run260.install(module)

        def later_provider_pool(*args, **kwargs):
            module.GEMINI_USAGE_AUDIT.records.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "gemini-3.7-flash",
                "kind": kwargs.get("request_kind") or (args[2] if len(args) >= 3 else "deep_dive"),
                "context": "SECRET ARTICLE TITLE MUST NOT PERSIST",
                "outcome": "success",
                "error_type": "",
            })
            return "ok", "gemini-3.7-flash"

        module._call_model_pool = later_provider_pool
        with patch.object(run260, "_persist_provider_health_history") as persist:
            result = module._call_deep_dive_pool("prompt", None, "deep_dive", request_context="live")

        self.assertEqual(result, ("ok", "gemini-3.7-flash"))
        persisted_rows = module._provider_health_history
        self.assertEqual(persisted_rows[-1]["model"], "gemini-3.7-flash")
        self.assertEqual(persisted_rows[-1]["outcome"], "success")
        self.assertNotIn("context", persisted_rows[-1])
        persist.assert_called_once_with(module)

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

    def test_37_and_38_daily_budgets_are_independent(self):
        module, _, _ = self._fake_pipeline()
        with patch.dict(
            os.environ,
            {
                "GEMINI_37_FLASH_DAILY_BUDGET": "13",
                "GEMINI_38_FLASH_DAILY_BUDGET": "7",
            },
            clear=False,
        ):
            run260.install(module)
        self.assertEqual(module.MODEL_DAILY_BUDGETS["gemini-3.7-flash"], 13)
        self.assertEqual(module.MODEL_DAILY_BUDGETS["gemini-3.8-flash"], 7)
        self.assertEqual(module.PERSISTENT_GEMINI_COUNTER.model_budgets["gemini-3.7-flash"], 13)
        self.assertEqual(module.PERSISTENT_GEMINI_COUNTER.model_budgets["gemini-3.8-flash"], 7)

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

    def test_main_eyecatch_branch_defaults_health_state_to_runtime_state(self):
        module, _, _ = self._fake_pipeline()
        module.requests = object()
        module.EYECATCH_GITHUB_BRANCH = "main"
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "trendhub-ab/ai-intelligence-factory",
                "GH_PAT": "test-token",
                "AIIF_RUNTIME_STATE_BRANCH": "",
            },
            clear=False,
        ):
            location = run260._health_state_location(module)
        self.assertIsNotNone(location)
        self.assertEqual(location[2], "runtime-state")

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
