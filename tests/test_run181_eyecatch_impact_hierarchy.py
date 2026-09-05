from __future__ import annotations

import inspect
import tempfile
import types
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as r178
import run181_eyecatch_visual_balance as r181


class Run181EyecatchImpactHierarchyTests(unittest.TestCase):
    def _plan(self):
        return {
            "eyecatch_title": "PolarsはなぜPandasより速いのか",
            "title_lines": ["Polarsはなぜ", "Pandasより速いのか"],
            "title_font_size": 70,
            "title_line_gap": 12,
            "subheadline_lines": ["違いと使いどころを、わかりやすく整理する"],
            "subheadline_font_size": 26,
        }

    def test_adopted_copy_hierarchy_is_deterministic_and_article_safe(self):
        self.assertEqual(
            r181._editorial_hook("PolarsはなぜPandasより速いのか", "", "DEV TOOLS"),
            "結局、何がすごいのか？",
        )
        self.assertEqual(
            r181._editorial_badge("AとBの違いを比較", "", "AI & TECH"),
            "比較で理解",
        )
        self.assertEqual(
            r181._editorial_badge("新しい研究", "", "RESEARCH"),
            "論文をやさしく",
        )
        self.assertEqual(
            r181._editorial_hook("脆弱性を検証する", "", "SECURITY"),
            "まず、何が危ないのか？",
        )

    def test_main_copy_scales_up_when_geometry_allows(self):
        size = r181._impact_title_size(
            ["Polarsはなぜ", "Pandasより速いのか"],
            66,
            12,
        )
        self.assertGreater(size, 66)
        self.assertLessEqual(size, r181.IMPACT_TITLE_MAX_FONT)

    def test_render_keeps_approved_right_side_and_adds_orange_impact(self):
        category = "DEV TOOLS"
        date_label = "2026.09"
        accent = ee._CATEGORY_ACCENTS[category]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "impact.png")
            r181.HIGHLIGHT_FONT_SCALE = 1.20
            r181._render_balanced_plan(
                "PolarsはなぜPandasより速いのか",
                "違いと使いどころを、わかりやすく整理する。",
                path,
                self._plan(),
                category=category,
                date_label=date_label,
                highlight_text="速いのか",
            )
            with Image.open(path) as rendered:
                actual = rendered.convert("RGB")

            expected = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (252, 253, 255))
            draw = ImageDraw.Draw(expected)
            ee._draw_network_illustration(draw, accent)
            ee._draw_brand(draw, accent)
            ee._draw_tags(draw, category, date_label, accent)

            # The adopted hierarchy is left-only. The approved illustration/top-right tags
            # must remain pixel-identical on the right side.
            right_box = (820, 0, ee.WIDTH, ee.HEIGHT)
            self.assertIsNone(ImageChops.difference(actual.crop(right_box), expected.crop(right_box)).getbbox())

            # Foreground hierarchy must materially change the left surface.
            left_box = (0, 90, 810, ee.HEIGHT)
            self.assertIsNotNone(ImageChops.difference(actual.crop(left_box), expected.crop(left_box)).getbbox())

            orange_hits = 0
            for pixel in actual.getdata():
                if all(abs(int(pixel[i]) - r181.HIGHLIGHT_ORANGE[i]) <= 3 for i in range(3)):
                    orange_hits += 1
            self.assertGreater(orange_hits, 20)

    def test_subheadline_falls_back_to_existing_source_bounded_copy(self):
        probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
        draw = ImageDraw.Draw(probe)
        lines, size = r181._subheadline_lines(
            draw,
            "PolarsはなぜPandasより速いのか",
            "PolarsとPandasの設計上の違いを整理する。余計な文章。",
            {"eyecatch_title": "PolarsはなぜPandasより速いのか"},
        )
        self.assertTrue(lines)
        self.assertLessEqual(len(lines), 2)
        self.assertEqual(size, 26)
        self.assertIn("Polars", "".join(lines))

    def test_install_is_idempotent_and_adds_no_provider_call_surface(self):
        pipeline = types.SimpleNamespace()
        original = r178._render_with_validated_plan
        try:
            first = r181.install(pipeline)
            installed = r178._render_with_validated_plan
            second = r181.install(pipeline)
            self.assertIs(first, pipeline)
            self.assertIs(second, pipeline)
            self.assertIs(r178._render_with_validated_plan, installed)
            self.assertTrue(pipeline.RUN181_EYECATCH_IMPACT_HIERARCHY)
            self.assertTrue(pipeline.RUN181_EYECATCH_BACKGROUND_UNCHANGED)
        finally:
            r178._render_with_validated_plan = original

        source = inspect.getsource(r181)
        self.assertNotIn("generateContent", source)
        self.assertNotIn("call_gemini", source)
        self.assertNotIn("_generate_via_chat", source)


if __name__ == "__main__":
    unittest.main()
