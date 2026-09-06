import os
import types
import unittest
from unittest.mock import patch

import run260_gemini_model_routing as run260


class Run260GeminiModelRoutingTests(unittest.TestCase):
    def _fake_pipeline(self, pool=None):
        calls = []

        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return "response", "model"

        persistent = types.SimpleNamespace(model_budgets={})
        module = types.SimpleNamespace(
            _call_model_pool=original,
            DEEP_DIVE_MODEL_POOL=list(pool or ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash"]),
            DEEP_DIVE_MODEL_CANDIDATES=list(pool or []),
            MODEL_DAILY_BUDGETS={
                "gemini-3.6-flash": 18,
                "gemini-3.7-flash": 18,
                "gemini-3.5-flash": 18,
            },
            PERSISTENT_GEMINI_COUNTER=persistent,
        )
        return module, calls

    def test_fresh_deep_dive_contract_is_37_then_38_then_36_then_35(self):
        module, _ = self._fake_pipeline()
        run260.install(module)
        self.assertEqual(
            module.DEEP_DIVE_MODEL_POOL[:4],
            [
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
            ],
        )

    def test_quality_retry_prefers_38_without_creating_new_call_path(self):
        module, calls = self._fake_pipeline()
        run260.install(module)
        result = module._call_model_pool(
            "prompt", None, "quality_retry", 0, module.DEEP_DIVE_MODEL_POOL,
            deep_dive=True, request_context="unit",
        )
        self.assertEqual(result, ("response", "model"))
        self.assertEqual(len(calls), 1)
        routed_pool = calls[0][0][4]
        self.assertEqual(
            routed_pool[:4],
            [
                "gemini-3.8-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
            ],
        )

    def test_normal_deep_dive_does_not_get_quality_retry_reordering(self):
        module, calls = self._fake_pipeline()
        run260.install(module)
        module._call_model_pool(
            "prompt", None, "deep_dive", 0, module.DEEP_DIVE_MODEL_POOL,
            deep_dive=True,
        )
        self.assertEqual(calls[0][0][4][0], "gemini-3.7-flash")

    def test_38_budget_is_explicit_and_cannot_exceed_18(self):
        module, _ = self._fake_pipeline()
        with patch.dict(os.environ, {"GEMINI_38_FLASH_DAILY_BUDGET": "999"}, clear=False):
            run260.install(module)
        self.assertEqual(module.MODEL_DAILY_BUDGETS["gemini-3.8-flash"], 18)
        self.assertEqual(module.PERSISTENT_GEMINI_COUNTER.model_budgets["gemini-3.8-flash"], 18)

    def test_operator_can_lower_38_budget(self):
        module, _ = self._fake_pipeline()
        with patch.dict(os.environ, {"GEMINI_38_FLASH_DAILY_BUDGET": "7"}, clear=False):
            run260.install(module)
        self.assertEqual(module.MODEL_DAILY_BUDGETS["gemini-3.8-flash"], 7)

    def test_screening_pool_and_gate_surfaces_are_not_touched(self):
        module, _ = self._fake_pipeline()
        module.SCREENING_MODEL_POOL = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
        module.MIN_PAID_AREA_LENGTH = 1200
        module.MAX_QUALITY_RETRIES = 1
        before_screening = list(module.SCREENING_MODEL_POOL)
        before_gate = (module.MIN_PAID_AREA_LENGTH, module.MAX_QUALITY_RETRIES)
        run260.install(module)
        self.assertEqual(module.SCREENING_MODEL_POOL, before_screening)
        self.assertEqual((module.MIN_PAID_AREA_LENGTH, module.MAX_QUALITY_RETRIES), before_gate)

    def test_install_is_idempotent(self):
        module, _ = self._fake_pipeline()
        run260.install(module)
        wrapped = module._call_model_pool
        run260.install(module)
        self.assertIs(module._call_model_pool, wrapped)


if __name__ == "__main__":
    unittest.main()
