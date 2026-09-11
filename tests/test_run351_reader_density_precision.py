from __future__ import annotations

import unittest

from reader_quality_precision import correct_reader_signals


class Run351ReaderDensityPrecisionTests(unittest.TestCase):
    def _base(self, **overrides):
        base = {
            "technical_terms_per_1000_chars": 26.7,
            "opening_technical_terms_per_1000_chars": 35.7,
            "plain_language_bridge_present": True,
            "jargon_dense_paragraph_count": 4,
            "implementation_identifier_count": 0,
            "analogy_hits": 1,
            "analogy_used": True,
            "unexplained_jargon": ["A4", "MIT"],
            "opening_non_engineer_access": "REVIEW",
            "jargon_translation": "REVIEW",
            "non_engineer_core_clarity": "REVIEW",
            "plain_language_bridge": "GOOD",
            "accessibility_issues": [
                "unexplained_acronyms",
                "jargon_translation_weak",
                "opening_non_engineer_access_weak",
            ],
            "accessibility": "REVIEW",
            "enjoyment_issues": [],
            "reader_enjoyment": "GOOD",
            "information_budget": "REVIEW",
            "max_explanatory_paragraph_run": 2,
            "reader_temperature_rhythm": "GOOD",
            "narrative_pull": "GOOD",
        }
        base.update(overrides)
        return base

    def _run38_like_article(self):
        return """自社のプロダクトや業務にAIを組み込むとき、意思決定者が悩むのは賢さだけではありません。運用コストも判断材料です。

## DeepSeek v4.1 Flashをどう見るか
Artificial AnalysisはDeepSeek v4.1 Flash Reasoning Max Effortのベンチマークデータを公開しました。この結果はモデル選定の比較材料になります。

## 大きいモデルでも使う部分は限られる
DeepSeek v4.1 Flashは多数のパラメータを持ちます。たとえば巨大な図書館でも、その瞬間に必要な本だけ開くようなものです。

## Intelligence Indexの位置
Artificial AnalysisのIntelligence IndexではDeepSeek v4.1 Flashを他のオープンウェイトモデルと比較できます。

## 導入前に見る条件
仕様書をA4用紙に印刷して確認するように、条件を順に確認します。MITライセンスで提供される点も利用条件の一つです。

つまり、いきなり全面導入するのではなく小さく試します。自社データで速度、品質、費用を比較して判断します。
"""

    def test_real_run38_shape_is_not_rejected_by_compound_labels_and_local_density(self):
        signals = correct_reader_signals(self._run38_like_article(), self._base())
        self.assertEqual([], signals["unexplained_jargon"])
        self.assertEqual("GOOD", signals["opening_non_engineer_access"])
        self.assertEqual("GOOD", signals["jargon_translation"])
        self.assertEqual("GOOD", signals["non_engineer_core_clarity"])
        self.assertEqual("GOOD", signals["information_budget"])
        self.assertEqual("GOOD", signals["accessibility"])
        self.assertEqual(1, signals["run351_effective_dense_paragraph_count"])
        self.assertTrue(signals["run351_reader_density_precision"])

    def test_bare_a4_and_mit_remain_unexplained(self):
        article = "自社の業務で判断します。A4とMITを確認します。たとえば小さく検証します。"
        signals = correct_reader_signals(article, self._base(jargon_dense_paragraph_count=1))
        self.assertEqual(["A4", "MIT"], signals["unexplained_jargon"])
        self.assertEqual("REVIEW", signals["accessibility"])
        self.assertIn("unexplained_acronyms", signals["accessibility_issues"])

    def test_real_unexplained_acronym_remains_blocking(self):
        article = self._run38_like_article().replace("A4用紙", "XYZ方式").replace("MITライセンス", "公開ライセンス")
        signals = correct_reader_signals(article, self._base(unexplained_jargon=["XYZ"], jargon_dense_paragraph_count=4))
        self.assertEqual(["XYZ"], signals["unexplained_jargon"])
        self.assertEqual("REVIEW", signals["jargon_translation"])
        self.assertEqual("REVIEW", signals["non_engineer_core_clarity"])

    def test_high_global_density_is_not_rescued(self):
        signals = correct_reader_signals(
            self._run38_like_article(),
            self._base(technical_terms_per_1000_chars=35.0),
        )
        self.assertEqual(4, signals["run351_effective_dense_paragraph_count"])
        self.assertEqual("REVIEW", signals["jargon_translation"])

    def test_implementation_heavy_article_is_not_rescued(self):
        signals = correct_reader_signals(
            self._run38_like_article(),
            self._base(implementation_identifier_count=3),
        )
        self.assertEqual(4, signals["run351_effective_dense_paragraph_count"])
        self.assertEqual("REVIEW", signals["jargon_translation"])

    def test_missing_plain_bridge_is_not_rescued(self):
        signals = correct_reader_signals(
            "自社の業務で判断します。\n\n専門仕様を列挙します。",
            self._base(plain_language_bridge_present=False, unexplained_jargon=[], jargon_dense_paragraph_count=4),
        )
        self.assertEqual(4, signals["run351_effective_dense_paragraph_count"])
        self.assertEqual("REVIEW", signals["jargon_translation"])

    def test_too_many_dense_paragraphs_are_not_rescued(self):
        signals = correct_reader_signals(
            self._run38_like_article(),
            self._base(jargon_dense_paragraph_count=5),
        )
        self.assertEqual(5, signals["run351_effective_dense_paragraph_count"])
        self.assertEqual("REVIEW", signals["jargon_translation"])

    def test_high_density_opening_is_not_rescued_even_with_business_language(self):
        signals = correct_reader_signals(
            self._run38_like_article(),
            self._base(opening_technical_terms_per_1000_chars=55.0),
        )
        self.assertEqual("REVIEW", signals["opening_non_engineer_access"])
        self.assertEqual(4, signals["run351_effective_dense_paragraph_count"])


if __name__ == "__main__":
    unittest.main()
