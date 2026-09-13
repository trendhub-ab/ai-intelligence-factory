from __future__ import annotations

import types
import unittest

import run408_approved_quality_fallback as run408


class Run408ApprovedQualityFallbackTests(unittest.TestCase):
    def _pipeline(self):
        p = types.SimpleNamespace()
        p.DEEP_DIVE_MODEL_POOL = [
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
        ]
        p.calls = []
        p.original_calls = []
        p.logger = types.SimpleNamespace(info=lambda *args, **kwargs: None)

        def historical(prompt, config=None, kind="deep_dive", request_context="", request_origin="new"):
            p.original_calls.append((kind, request_origin))
            return "historical", "gemini-3.7-flash"

        def provider_pool(prompt, config, kind, reserve, pool, deep_dive=False,
                          request_context="", request_origin="new"):
            p.calls.append({
                "kind": kind,
                "pool": list(pool),
                "deep_dive": deep_dive,
                "origin": request_origin,
                "reserve": reserve,
            })
            # Reproduce real Run #10 semantics: 3.7 reaches provider and 503s;
            # 3.6 is rejected by persistent cap before provider send; 3.5 succeeds.
            provider_visible = []
            for model in pool:
                if model == "gemini-3.7-flash":
                    provider_visible.append(model)
                    continue
                if model == "gemini-3.6-flash":
                    continue  # persistent cap: zero provider request
                if model == "gemini-3.5-flash":
                    provider_visible.append(model)
                    p.provider_visible = provider_visible
                    return "ok", model
            raise RuntimeError("3.5 fallback was stranded")

        p._call_deep_dive_pool = historical
        p._call_model_pool = provider_pool
        return p

    def test_approved_quality_retry_reaches_35_after_36_presend_cap(self):
        p = self._pipeline()
        run408.install(p)
        response, model = p._call_deep_dive_pool(
            "prompt", kind="quality_retry", request_origin="approved_article_apply"
        )
        self.assertEqual("ok", response)
        self.assertEqual("gemini-3.5-flash", model)
        self.assertEqual(
            ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.8-flash"],
            p.calls[0]["pool"],
        )
        self.assertEqual(["gemini-3.7-flash", "gemini-3.5-flash"], p.provider_visible)
        self.assertTrue(p.calls[0]["deep_dive"])
        self.assertEqual(0, p.calls[0]["reserve"])

    def test_normal_quality_retry_keeps_historical_run260_route(self):
        p = self._pipeline()
        run408.install(p)
        result = p._call_deep_dive_pool("prompt", kind="quality_retry", request_origin="new")
        self.assertEqual(("historical", "gemini-3.7-flash"), result)
        self.assertEqual([("quality_retry", "new")], p.original_calls)
        self.assertEqual([], p.calls)

    def test_approved_initial_deep_dive_keeps_historical_route(self):
        p = self._pipeline()
        run408.install(p)
        result = p._call_deep_dive_pool("prompt", kind="deep_dive", request_origin="approved_article_apply")
        self.assertEqual(("historical", "gemini-3.7-flash"), result)
        self.assertEqual([("deep_dive", "approved_article_apply")], p.original_calls)
        self.assertEqual([], p.calls)

    def test_install_is_idempotent(self):
        p = self._pipeline()
        run408.install(p)
        first = p._call_deep_dive_pool
        run408.install(p)
        self.assertIs(first, p._call_deep_dive_pool)

    def test_missing_provider_contract_fails_closed(self):
        p = types.SimpleNamespace(_call_deep_dive_pool=lambda *a, **k: None)
        with self.assertRaises(RuntimeError):
            run408.install(p)


if __name__ == "__main__":
    unittest.main()
