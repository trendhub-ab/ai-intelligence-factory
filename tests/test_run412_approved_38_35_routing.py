from __future__ import annotations

import os
import types
import unittest
from unittest.mock import patch

import run412_approved_38_35_routing as run412


class Run412ApprovedRoutingTests(unittest.TestCase):
    def _pipeline(self):
        calls = []
        p = types.SimpleNamespace()
        p.calls = calls
        p.logger = types.SimpleNamespace(info=lambda *a, **k: None)
        p._call_deep_dive_pool = lambda *a, **k: calls.append(("original", a, k)) or ("original", "m")
        p._call_model_pool = lambda *a, **k: calls.append(("model", a, k)) or ("model", a[4])
        return p

    def test_no_env_is_noop(self):
        p = self._pipeline()
        original = p._call_deep_dive_pool
        with patch.dict(os.environ, {}, clear=True):
            run412.install(p)
        self.assertIs(p._call_deep_dive_pool, original)

    def test_approved_initial_uses_38_then_35(self):
        p = self._pipeline()
        with patch.dict(os.environ, {run412.ENV_KEY: "gemini-3.8-flash,gemini-3.5-flash"}, clear=True):
            run412.install(p)
            p._call_deep_dive_pool("x", kind="deep_dive", request_origin="approved_article_apply")
        self.assertEqual(p.calls[-1][1][4], ["gemini-3.8-flash", "gemini-3.5-flash"])

    def test_approved_quality_retry_prefers_35_then_38(self):
        p = self._pipeline()
        with patch.dict(os.environ, {run412.ENV_KEY: "gemini-3.8-flash,gemini-3.5-flash"}, clear=True):
            run412.install(p)
            p._call_deep_dive_pool("x", kind="quality_retry", request_origin="approved_article_apply")
        self.assertEqual(p.calls[-1][1][4], ["gemini-3.5-flash", "gemini-3.8-flash"])

    def test_other_origin_keeps_original_route(self):
        p = self._pipeline()
        with patch.dict(os.environ, {run412.ENV_KEY: "gemini-3.8-flash,gemini-3.5-flash"}, clear=True):
            run412.install(p)
            p._call_deep_dive_pool("x", kind="deep_dive", request_origin="new")
        self.assertEqual(p.calls[-1][0], "original")

    def test_unapproved_model_fails_closed(self):
        p = self._pipeline()
        with patch.dict(os.environ, {run412.ENV_KEY: "gemini-3.8-flash,gemini-3.7-flash"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "unapproved model"):
                run412.install(p)


if __name__ == "__main__":
    unittest.main()
