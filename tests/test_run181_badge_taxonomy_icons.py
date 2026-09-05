from __future__ import annotations

import inspect
import unittest

from PIL import Image, ImageDraw

import eyecatch_badge_taxonomy as taxonomy
import run181_eyecatch_visual_balance as run181


class Run181BadgeTaxonomyIconTests(unittest.TestCase):
    def test_beginner_is_explicit_not_generic_fallback(self):
        self.assertEqual(
            taxonomy.classify_badge("AIの基礎から学ぶ初心者入門", "", "AI & TECH"),
            "初心者向け",
        )
        self.assertEqual(
            taxonomy.classify_badge("AI業界で今起きていること", "重要な論点を整理する", "AI & TECH"),
            "要点を理解",
        )

    def test_badge_taxonomy_covers_major_editorial_purposes(self):
        cases = (
            ("PandasとPolarsを比較。違いは？", "", "AI & TECH", "比較で理解"),
            ("Prompt Injectionの新しい攻撃", "安全性を確認する", "SECURITY", "安全性を確認"),
            ("arXiv論文を読む", "研究の要点", "RESEARCH", "論文をやさしく"),
            ("GitHub CLIを開発で使う", "", "DEV TOOLS", "開発で使う"),
            ("RAGデータベースの設計", "", "DATA", "データを理解"),
            ("企業がAIを導入する前に", "運用コストを見る", "AI BUSINESS", "実務で判断"),
            ("新モデルを正式リリース", "提供開始を発表", "AI & TECH", "最新動向を理解"),
            ("LLMはなぜ速くなったのか", "推論の仕組み", "MODELS", "仕組みを理解"),
        )
        for title, summary, category, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(taxonomy.classify_badge(title, summary, category), expected)
                self.assertEqual(run181._editorial_badge(title, summary, category), expected)

    def test_every_label_has_a_nonblank_fixed_vector_icon(self):
        accent = (49, 104, 229)
        icon_fingerprints = set()
        for label in taxonomy.BADGE_LABELS:
            image = Image.new("RGB", (40, 40), (255, 255, 255))
            draw = ImageDraw.Draw(image)
            taxonomy.draw_badge_icon(draw, label, 7, 7, accent, size=26)
            pixels = tuple(image.getdata())
            self.assertTrue(any(pixel != (255, 255, 255) for pixel in pixels), label)
            icon_fingerprints.add(hash(pixels))
        self.assertGreaterEqual(len(icon_fingerprints), 9)

    def test_badge_layer_adds_no_provider_or_network_callsite(self):
        source = inspect.getsource(taxonomy) + "\n" + inspect.getsource(run181)
        forbidden = (
            "_generate_via_chat(",
            "call_gemini(",
            "generateContent",
            "urllib.request",
            "requests.get(",
            "requests.post(",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_run179_font_contract_is_not_replaced_by_badge_change(self):
        # Run181 must continue resolving fonts through editorial_eyecatch, which Run179 patches.
        source = inspect.getsource(run181)
        self.assertIn("ee._jp_font", source)
        self.assertIn("ee._latin_font", source)
        self.assertNotIn("ImageFont.truetype", source)


if __name__ == "__main__":
    unittest.main()
