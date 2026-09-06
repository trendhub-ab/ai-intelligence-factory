from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

import editorial_eyecatch as ee
import run180_eyecatch_semantic_layout as r180
import run181_eyecatch_visual_balance as r181


class Run181ThreeLineFallbackTests(unittest.TestCase):
    def test_semantic_prompt_prefers_two_lines_but_accepts_three(self):
        prompt = r180._layout_prompt("OpenAIの新しい音声AIは業務をどう変えるのか", "要点を整理する")
        self.assertIn("2行を第一選択", prompt)
        self.assertIn("必要な場合のみ3行", prompt)
        self.assertIn("3行は正常なfallback", prompt)

    def test_three_line_profile_is_a_normal_compact_fallback(self):
        profile = r181._impact_layout_profile(
            ["OpenAIの新しい", "音声AIは業務を", "どう変えるのか"],
            14,
        )
        self.assertEqual(profile["line_count"], 3)
        self.assertTrue(profile["is_three_line"])
        self.assertLessEqual(profile["line_gap"], r181.IMPACT_THREE_LINE_GAP_MAX)
        self.assertLessEqual(profile["title_max_font"], r181.IMPACT_TITLE_MAX_FONT)
        self.assertGreater(profile["title_safe_bottom"], r181.IMPACT_TITLE_SAFE_BOTTOM)
        self.assertGreaterEqual(profile["subtitle_min_top"], profile["title_safe_bottom"])

    def test_two_line_profile_keeps_primary_impact_geometry(self):
        profile = r181._impact_layout_profile(["Polarsはなぜ", "Pandasより速いのか"], 12)
        self.assertEqual(profile["line_count"], 2)
        self.assertFalse(profile["is_three_line"])
        self.assertEqual(profile["title_top"], r181.IMPACT_TITLE_TOP)
        self.assertEqual(profile["title_safe_bottom"], r181.IMPACT_TITLE_SAFE_BOTTOM)
        self.assertEqual(profile["title_max_font"], r181.IMPACT_TITLE_MAX_FONT)
        self.assertEqual(profile["line_gap"], 12)

    def test_three_line_render_is_publishable_and_right_side_is_unchanged(self):
        plan = {
            "eyecatch_title": "OpenAIの新しい音声AIは業務をどう変えるのか",
            "title_lines": ["OpenAIの新しい", "音声AIは業務を", "どう変えるのか"],
            "title_font_size": 60,
            "title_line_gap": 14,
            "subheadline_lines": ["強みと導入の現実を、わかりやすく整理する"],
            "subheadline_font_size": 26,
        }
        category = "MULTIMODAL"
        date_label = "2026.09"
        accent = ee._CATEGORY_ACCENTS[category]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "three_line.png")
            r181._render_balanced_plan(
                "OpenAIの新しい音声AIは業務をどう変えるのか",
                "強みと導入の現実を、わかりやすく整理する。",
                path,
                plan,
                category=category,
                date_label=date_label,
                highlight_text="変える",
            )
            with Image.open(path) as rendered:
                actual = rendered.convert("RGB")

            expected = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (252, 253, 255))
            draw = ImageDraw.Draw(expected)
            ee._draw_network_illustration(draw, accent)
            ee._draw_brand(draw, accent)
            ee._draw_tags(draw, category, date_label, accent)

            right_box = (820, 0, ee.WIDTH, ee.HEIGHT)
            self.assertIsNone(
                ImageChops.difference(actual.crop(right_box), expected.crop(right_box)).getbbox()
            )
            self.assertTrue(Path(path).exists())

    def test_policy_does_not_add_provider_surface(self):
        import inspect

        source = inspect.getsource(r181)
        self.assertNotIn("generateContent", source)
        self.assertNotIn("call_gemini", source)
        self.assertNotIn("_generate_via_chat", source)


if __name__ == "__main__":
    unittest.main()
