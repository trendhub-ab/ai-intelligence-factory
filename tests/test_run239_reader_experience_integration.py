from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import MagicMock

# Keep import safe on minimal/local environments that do not have google-genai.
try:
    import google.genai  # noqa: F401
except Exception:
    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    google_pkg.__path__ = getattr(google_pkg, "__path__", [])
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class _Client:
        def __init__(self, *args, **kwargs):
            self.chats = MagicMock()
    class _APIError(Exception):
        pass
    genai_mod.Client = _Client
    errors_mod.APIError = _APIError
    google_pkg.genai = genai_mod
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.errors"] = errors_mod

import pipeline
import reader_experience_signals as extracted


class Run239ReaderExperienceIntegrationTests(unittest.TestCase):
    def test_pipeline_alias_is_exact_canonical_function(self):
        self.assertIs(pipeline._reader_experience_signals_impl, extracted.reader_experience_signals)

    def test_wrapper_matches_module_on_representative_articles(self):
        articles = [
            """## 新しい仕組み\n\nAPIという言葉は難しそうですよね。簡単に言えば、店の受付のような仕組みです。\n\n実際の制約を確認すると、まず小さく試して比較するのが安全です。ただし全面導入を保証する話ではありません。\n\n私なら検証してから次の判断をします。""",
            """## Security update\n\nRFC 9999 API TLS ACL IAM RBAC SSO JWT GPU CPU DB HTTP HTTPS MODEL TOKEN。\n\n仕様を評価します。条件を解析します。構成を確認します。必要があります。方式です。発生します。\n\n導入前に比較対象を確認します。""",
            """発表されました。\n\n## 詳細\n\nこの技術は新しい仕組みです。今回の発表を確認します。今後に注目です。\n\n## まとめ\n\n判断します。""",
            "",
        ]
        for article in articles:
            with self.subTest(article=article[:30]):
                expected = extracted.reader_experience_signals(article, pipeline._article_opening_excerpt)
                actual = pipeline._reader_experience_signals(article)
                self.assertEqual(actual, expected)

    def test_live_opening_helper_binding_is_not_frozen_in_module(self):
        original = pipeline._article_opening_excerpt
        try:
            pipeline._article_opening_excerpt = lambda article, max_chars=700: "なぜ気になるのでしょうか？ スマホで使う場面を想像してください。"
            via_wrapper = pipeline._reader_experience_signals("## 技術\n\nAPI仕様です。まず比較します。ただし保証ではありません。")
            via_original = extracted.reader_experience_signals(
                "## 技術\n\nAPI仕様です。まず比較します。ただし保証ではありません。",
                original,
            )
            self.assertNotEqual(via_wrapper["curiosity_pull"], via_original["curiosity_pull"])
        finally:
            pipeline._article_opening_excerpt = original


if __name__ == "__main__":
    unittest.main()
