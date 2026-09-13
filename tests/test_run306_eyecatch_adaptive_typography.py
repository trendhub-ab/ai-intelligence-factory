from __future__ import annotations

import inspect
import unittest

import run181_eyecatch_visual_balance as r181
import run296_editorial_format_v2 as r296


class Run306EyecatchAdaptiveTypographyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            "_impact_title_size": r181._impact_title_size,
            "_impact_layout_profile": r181._impact_layout_profile,
            "IMPACT_TITLE_MAX_FONT": r181.IMPACT_TITLE_MAX_FONT,
            "IMPACT_THREE_LINE_TITLE_MAX_FONT": r181.IMPACT_THREE_LINE_TITLE_MAX_FONT,
            "IMPACT_HIGHLIGHT_MAX_FONT": r181.IMPACT_HIGHLIGHT_MAX_FONT,
        }
        self._optional_names = (
            "_RUN306_ADAPTIVE_TYPOGRAPHY_INSTALLED",
            "RUN306_TITLE_MAX_FONT",
            "RUN306_HIGHLIGHT_MAX_FONT",
            "RUN306_VISUAL_CENTER_Y",
        )
        self._optional_saved = {
            name: getattr(r181, name)
            for name in self._optional_names
            if hasattr(r181, name)
        }

    def tearDown(self) -> None:
        for name, value in self._saved.items():
            setattr(r181, name, value)
        for name in self._optional_names:
            if name in self._optional_saved:
                setattr(r181, name, self._optional_saved[name])
            elif hasattr(r181, name):
                delattr(r181, name)

    def _install(self) -> None:
        r296._install_run306_adaptive_typography(r181)

    def test_reference_netflix_scale_is_the_normal_title_ceiling(self):
        self._install()
        lines = list(r296.GENREC_EYECATCH_LINES)
        size = r181._impact_title_size(lines, 64, 10)
        self.assertEqual(size, r296.RUN306_TITLE_MAX_FONT)
        self.assertEqual(size, 72)
        self.assertEqual(r181.IMPACT_TITLE_MAX_FONT, 72)
        self.assertEqual(r181.IMPACT_THREE_LINE_TITLE_MAX_FONT, 72)
        self.assertEqual(r181.IMPACT_HIGHLIGHT_MAX_FONT, 86)

    def test_font_size_is_driven_by_text_geometry_not_model_hint(self):
        self._install()
        lines = ["AIに本番DBの鍵をそのまま渡していませんか？", "運用前に権限設計を確認する"]
        from_small_hint = r181._impact_title_size(lines, 50, 12)
        from_large_hint = r181._impact_title_size(lines, 70, 12)
        self.assertEqual(from_small_hint, from_large_hint)
        self.assertLessEqual(from_small_hint, r296.RUN306_TITLE_MAX_FONT)
        self.assertGreaterEqual(from_small_hint, r296.RUN306_TITLE_MIN_FONT)

    def test_two_and_three_line_blocks_share_one_visual_center(self):
        two_top = r296.adaptive_title_top(140, r181.IMPACT_TITLE_TOP, r181.IMPACT_TITLE_SAFE_BOTTOM)
        three_top = r296.adaptive_title_top(
            210,
            r181.IMPACT_THREE_LINE_TITLE_TOP,
            r181.IMPACT_THREE_LINE_SAFE_BOTTOM,
        )
        self.assertEqual(two_top + 70, r296.RUN306_VISUAL_CENTER_Y)
        self.assertEqual(three_top + 105, r296.RUN306_VISUAL_CENTER_Y)
        self.assertGreater(two_top, r181.IMPACT_TITLE_TOP)
        self.assertGreater(three_top, r181.IMPACT_THREE_LINE_TITLE_TOP)

    def test_real_three_line_profile_moves_down_from_old_fixed_anchor(self):
        self._install()
        profile = r181._impact_layout_profile(list(r296.GENREC_EYECATCH_LINES), 10)
        self.assertTrue(profile["is_three_line"])
        self.assertGreater(profile["title_top"], r181.IMPACT_THREE_LINE_TITLE_TOP)
        self.assertLess(profile["title_top"], profile["title_safe_bottom"])

    def test_run306_adds_no_provider_or_note_mutation_surface(self):
        source = inspect.getsource(r296)
        for forbidden in (
            "generateContent",
            "_generate_via_chat(",
            "generate_content(",
            "page.click(",
            "publish_note",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
